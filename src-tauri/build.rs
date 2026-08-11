fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&["library_choose_root", "library_import_root"]),
    ))
    .expect("failed to configure APPLAYLIST desktop host build");
}
