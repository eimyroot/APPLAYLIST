mod library_capability;
mod sidecar_bridge;

use library_capability::LibraryCapabilityRegistry;
use sidecar_bridge::SidecarBridge;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(LibraryCapabilityRegistry::default())
        .manage(SidecarBridge::from_environment())
        .invoke_handler(tauri::generate_handler![
            library_capability::library_choose_root,
            sidecar_bridge::library_import_root
        ])
        .run(tauri::generate_context!())
        .expect("error while running APPLAYLIST desktop host");
}
