mod analysis_bridge;
mod analysis_job;
mod import_job;
mod library_capability;
mod playlist_editor;
mod set_proposal;
mod sidecar_bridge;

use analysis_bridge::AnalysisSidecarBridge;
use analysis_job::AnalysisJobRegistry;
use import_job::ImportJobRegistry;
use library_capability::LibraryCapabilityRegistry;
use playlist_editor::PlaylistEditorBridge;
use set_proposal::SetProposalBridge;
use sidecar_bridge::SidecarBridge;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(LibraryCapabilityRegistry::default())
        .manage(ImportJobRegistry::default())
        .manage(AnalysisJobRegistry::default())
        .manage(SidecarBridge::from_environment())
        .manage(AnalysisSidecarBridge::from_environment())
        .manage(SetProposalBridge::from_environment())
        .manage(PlaylistEditorBridge::from_environment())
        .invoke_handler(tauri::generate_handler![
            library_capability::library_choose_root,
            import_job::library_import_start,
            import_job::library_import_status,
            import_job::library_import_cancel,
            analysis_job::analysis_start,
            analysis_job::analysis_status,
            analysis_job::analysis_cancel,
            analysis_job::analysis_inspector_list,
            analysis_job::analysis_inspector_get,
            analysis_job::analysis_correct,
            analysis_job::analysis_reanalyze,
            set_proposal::set_proposal_generate,
            playlist_editor::playlist_editor_accept,
            playlist_editor::playlist_editor_reorder,
            playlist_editor::playlist_editor_lock,
            playlist_editor::playlist_editor_replace,
            playlist_editor::playlist_editor_history
        ])
        .run(tauri::generate_context!())
        .expect("error while running APPLAYLIST desktop host");
}
