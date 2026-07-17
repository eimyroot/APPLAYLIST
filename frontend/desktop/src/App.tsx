import { useEffect, useState } from "react";

import {
  chooseLibraryRoot,
  getDesktopStatus,
  type DesktopStatus,
  type LibraryRootCapability,
} from "./desktopBridge";

type ViewState =
  | { kind: "loading" }
  | { kind: "ready"; status: DesktopStatus }
  | { kind: "error"; message: string };

function safeMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Desktop host request failed";
}

export function App() {
  const [view, setView] = useState<ViewState>({ kind: "loading" });
  const [capability, setCapability] = useState<LibraryRootCapability | null>(null);
  const [selecting, setSelecting] = useState(false);

  useEffect(() => {
    let active = true;
    void getDesktopStatus()
      .then((status) => {
        if (active) {
          setView({ kind: "ready", status });
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setView({ kind: "error", message: safeMessage(error) });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function selectLibraryRoot() {
    setSelecting(true);
    try {
      const selected = await chooseLibraryRoot();
      setCapability(selected);
      const status = await getDesktopStatus();
      setView({ kind: "ready", status });
    } catch (error: unknown) {
      setView({ kind: "error", message: safeMessage(error) });
    } finally {
      setSelecting(false);
    }
  }

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">Bundle 48 host proof</p>
        <h1>APPLAYLIST</h1>
        <p className="lede">
          Minimal renderer with typed commands and no direct filesystem or sidecar authority.
        </p>
      </header>

      <section className="panel" aria-live="polite">
        <h2>Desktop host</h2>
        {view.kind === "loading" && <p>Checking host boundary…</p>}
        {view.kind === "error" && <p role="alert">{view.message}</p>}
        {view.kind === "ready" && (
          <dl>
            <div>
              <dt>Protocol</dt>
              <dd>{view.status.protocol}</dd>
            </div>
            <div>
              <dt>State</dt>
              <dd>{view.status.state}</dd>
            </div>
            <div>
              <dt>Capabilities</dt>
              <dd>{view.status.capabilityCount}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="panel">
        <h2>Library root capability</h2>
        <p>
          The native host selects and retains the real directory. The renderer receives only an
          opaque identifier and a display name.
        </p>
        <button type="button" onClick={() => void selectLibraryRoot()} disabled={selecting}>
          {selecting ? "Opening native dialog…" : "Choose library folder"}
        </button>
        {capability !== null && (
          <dl className="capability">
            <div>
              <dt>Display name</dt>
              <dd>{capability.displayName}</dd>
            </div>
            <div>
              <dt>Capability ID</dt>
              <dd>{capability.capabilityId}</dd>
            </div>
          </dl>
        )}
      </section>
    </main>
  );
}
