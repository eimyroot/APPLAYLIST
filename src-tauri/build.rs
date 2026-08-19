fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "library_choose_root",
            "library_import_start",
            "library_import_status",
            "library_import_cancel",
            "analysis_start",
            "analysis_status",
            "analysis_cancel",
            "analysis_inspector_list",
            "analysis_inspector_get",
            "analysis_correct",
            "analysis_reanalyze",
            "set_proposal_generate",
            "playlist_editor_accept",
            "playlist_editor_reorder",
            "playlist_editor_lock",
            "playlist_editor_replace",
            "playlist_editor_history",
        ]),
    ))
    .expect("failed to configure APPLAYLIST desktop host build");
}
