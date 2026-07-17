from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from core.desktop.protocol import SidecarReadinessEnvelope, SidecarSession


class ChildProcess(Protocol):
    @property
    def pid(self) -> int: ...

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class SidecarState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SupervisorPolicy:
    startup_timeout_seconds: float = 15.0
    poll_interval_seconds: float = 0.1
    graceful_shutdown_seconds: float = 5.0
    max_restarts: int = 2

    def __post_init__(self) -> None:
        if self.startup_timeout_seconds <= 0:
            raise ValueError("startup timeout must be positive")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll interval must be positive")
        if self.graceful_shutdown_seconds <= 0:
            raise ValueError("graceful shutdown timeout must be positive")
        if not isinstance(self.max_restarts, int) or isinstance(self.max_restarts, bool):
            raise TypeError("max_restarts must be an integer")
        if self.max_restarts < 0:
            raise ValueError("max_restarts must not be negative")


class SidecarSupervisorError(RuntimeError):
    pass


class SidecarSupervisor:
    def __init__(
        self,
        *,
        spawn: Callable[[SidecarSession], ChildProcess],
        readiness_probe: Callable[[SidecarSession], SidecarReadinessEnvelope],
        request_shutdown: Callable[[SidecarSession], None],
        policy: SupervisorPolicy | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._spawn = spawn
        self._readiness_probe = readiness_probe
        self._request_shutdown = request_shutdown
        self._policy = policy or SupervisorPolicy()
        self._monotonic = monotonic
        self._sleep = sleep
        self._session: SidecarSession | None = None
        self._process: ChildProcess | None = None
        self._state = SidecarState.STOPPED
        self._restart_count = 0

    @property
    def state(self) -> SidecarState:
        return self._state

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def restart_count(self) -> int:
        return self._restart_count

    def start(self) -> SidecarReadinessEnvelope:
        if self._process is not None and self._process.poll() is None:
            raise SidecarSupervisorError("sidecar is already running")

        self._state = SidecarState.STARTING
        self._session = SidecarSession.generate()
        self._process = self._spawn(self._session)
        deadline = self._monotonic() + self._policy.startup_timeout_seconds
        last_error: Exception | None = None

        while self._monotonic() < deadline:
            if self._process.poll() is not None:
                self._state = SidecarState.FAILED
                raise SidecarSupervisorError("sidecar exited before readiness")
            try:
                envelope = self._readiness_probe(self._session)
                envelope.validate_for_session(self._session)
                if envelope.ready_state == "ready":
                    self._state = SidecarState.READY
                    return envelope
                if envelope.ready_state == "degraded":
                    self._state = SidecarState.DEGRADED
                    return envelope
            except Exception as exc:
                last_error = exc
            self._sleep(self._policy.poll_interval_seconds)

        self._state = SidecarState.FAILED
        self._terminate_owned_process()
        message = "sidecar readiness timed out"
        if last_error is not None:
            message = f"{message}: {type(last_error).__name__}"
        raise SidecarSupervisorError(message)

    def restart(self) -> SidecarReadinessEnvelope:
        if self._restart_count >= self._policy.max_restarts:
            self._state = SidecarState.FAILED
            raise SidecarSupervisorError("sidecar restart budget exhausted")
        self.stop()
        self._restart_count += 1
        return self.start()

    def stop(self) -> None:
        if self._process is None:
            self._state = SidecarState.STOPPED
            self._session = None
            return

        self._state = SidecarState.STOPPING
        process = self._process
        session = self._session
        if process.poll() is None and session is not None:
            try:
                self._request_shutdown(session)
                process.wait(timeout=self._policy.graceful_shutdown_seconds)
            except Exception:
                try:
                    process.terminate()
                    process.wait(timeout=self._policy.graceful_shutdown_seconds)
                except Exception:
                    process.kill()
                    process.wait(timeout=self._policy.graceful_shutdown_seconds)

        self._process = None
        self._session = None
        self._state = SidecarState.STOPPED

    def _terminate_owned_process(self) -> None:
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=self._policy.graceful_shutdown_seconds)
            except Exception:
                process.kill()
                process.wait(timeout=self._policy.graceful_shutdown_seconds)
        self._process = None
        self._session = None
