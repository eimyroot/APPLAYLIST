import { invoke } from "@tauri-apps/api/core";

export interface DesktopStatus {
  protocol: "applaylist-desktop-v1";
  state: "host-ready";
  capabilityCount: number;
}

export interface LibraryRootCapability {
  capabilityId: string;
  displayName: string;
}

export function getDesktopStatus(): Promise<DesktopStatus> {
  return invoke<DesktopStatus>("desktop_status");
}

export function chooseLibraryRoot(): Promise<LibraryRootCapability | null> {
  return invoke<LibraryRootCapability | null>("choose_library_root");
}
