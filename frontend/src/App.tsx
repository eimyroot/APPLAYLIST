import { useCallback, useEffect, useState } from "react";

import {
  desktopBridge,
  type AuthenticatedSidecarHealth,
  type LibraryRootCapability,
  type ShellStatus,
} from "./desktopBridge";
import "./styles.css";

export function App() {
  const [shellStatus, setShellStatus] = useState<ShellStatus | null>(null);
  const [health, setHealth] = useState<AuthenticatedSidecarHealth | null>(null);
  const [libraryCapability, setLibraryCapability] =
    useState<LibraryRootCapability | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    setError(null);
    try {
      setShellStatus(await desktopBridge.getShellStatus());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  async function checkHealth() {
    setError(null);
    try {
      setHealth(await desktopBridge.checkSidecarHealth());
      await refreshStatus();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  async function chooseLibraryRoot() {
    setError(null);
    try {
      setLibraryCapability(await desktopBridge.chooseLibraryRoot());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <main className="proof-shell">
      <header>
        <p className="eyebrow">Bundle 48 security proof</p>
        <h1>APPLAYLIST Desktop Boundary</h1>
        <p>
          This screen can call only named Tauri commands. It does not know the
          Python sidecar URL, session secret, SQLite path, or selected host path.
        </p>
      </header>

      <section aria-labelledby="sidecar-heading">
        <h2 id="sidecar-heading">Sidecar lifecycle</h2>
        <dl>
          <div>
            <dt>State</dt>
            <dd>{shellStatus?.sidecarState ?? "loading"}</dd>
          </div>
          <div>
            <dt>Protocol</dt>
            <dd>{shellStatus?.protocolVersion ?? "—"}</dd>
          </div>
          <div>
            <dt>Service</dt>
            <dd>{shellStatus?.sidecarServiceVersion ?? "—"}</dd>
          </div>
          <div>
            <dt>Startup</dt>
            <dd>
              {shellStatus?.startupMs == null
                ? "—"
                : `${shellStatus.startupMs.toFixed(1)} ms`}
            </dd>
          </div>
        </dl>
        <div className="actions">
          <button type="button" onClick={() => void refreshStatus()}>
            Refresh shell status
          </button>
          <button type="button" onClick={() => void checkHealth()}>
            Authenticated health check
          </button>
        </div>
        {health ? (
          <p className="success" role="status">
            Sidecar authenticated on {health.bindScope}; PID {health.pid}.
          </p>
        ) : null}
      </section>

      <section aria-labelledby="capability-heading">
        <h2 id="capability-heading">Filesystem capability</h2>
        <p>
          Folder selection is owned by the desktop core. The renderer receives
          only an opaque session capability and a display label.
        </p>
        <button type="button" onClick={() => void chooseLibraryRoot()}>
          Choose library folder
        </button>
        {libraryCapability ? (
          <dl>
            <div>
              <dt>Capability</dt>
              <dd className="monospace">{libraryCapability.capabilityId}</dd>
            </div>
            <div>
              <dt>Label</dt>
              <dd>{libraryCapability.displayLabel}</dd>
            </div>
            <div>
              <dt>Operations</dt>
              <dd>{libraryCapability.allowedOperations.join(", ")}</dd>
            </div>
          </dl>
        ) : null}
      </section>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </main>
  );
}
