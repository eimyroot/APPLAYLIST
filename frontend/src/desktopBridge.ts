import { invoke } from "@tauri-apps/api/core";

export type SidecarState =
  | "not_started"
  | "starting"
  | "ready"
  | "degraded"
  | "stopping"
  | "stopped"
  | "failed";

export interface ShellStatus {
  shellVersion: string;
  protocolVersion: string;
  sidecarState: SidecarState;
  sidecarServiceVersion: string | null;
  sidecarPid: number | null;
  startupMs: number | null;
  lastErrorCode: string | null;
}

export interface LibraryRootCapability {
  capabilityId: string;
  displayLabel: string;
  allowedOperations: readonly ["library.scan", "library.read"];
  sessionScoped: true;
}

export interface AuthenticatedSidecarHealth {
  status: "ready";
  protocolVersion: string;
  serviceVersion: string;
  processNonce: string;
  pid: number;
  bindScope: "loopback";
}

export const desktopBridge = {
  getShellStatus(): Promise<ShellStatus> {
    return invoke<ShellStatus>("get_shell_status");
  },

  chooseLibraryRoot(): Promise<LibraryRootCapability | null> {
    return invoke<LibraryRootCapability | null>("choose_library_root");
  },

  checkSidecarHealth(): Promise<AuthenticatedSidecarHealth> {
    return invoke<AuthenticatedSidecarHealth>("check_sidecar_health");
  },
} as const;
