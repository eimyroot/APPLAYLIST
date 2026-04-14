from __future__ import annotations

from collections import deque
from typing import Any


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._queue: deque[dict[str, Any]] = deque()

    def enqueue(self, payload: dict[str, Any]) -> None:
        self._queue.append(payload)

    def dequeue(self) -> dict[str, Any] | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def size(self) -> int:
        return len(self._queue)

    def clear(self) -> None:
        self._queue.clear()


job_queue = InMemoryJobQueue()
