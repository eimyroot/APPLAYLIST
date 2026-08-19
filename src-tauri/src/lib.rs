mod analysis_bridge;
mod analysis_job;
mod import_job;
mod library_capability;
mod playlist_editor;
mod playlist_evidence_export;
mod playlist_export;
mod playlist_vendor_interop;
mod set_proposal;
mod sidecar_bridge;
mod transition_inspector;

use analysis_bridge::AnalysisSidecarBridge;
use analysis_job::AnalysisJobRegistry;
use import_job::ImportJobRegistry;
use library_capability::LibraryCapabilityRegistry;
use playlist_editor::PlaylistEditorBridge;
use playlist_evidence_export::PlaylistEvidenceExportBridge;
use playlist_export::PlaylistExportBridge;
use playlist_vendor_interop::PlaylistVendorInteropBridge;
use set_proposal::SetProposalBridge;
use sidecar_bridge::SidecarBridge;
use transition_inspector::TransitionInspectorBridge;

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
        .manage(PlaylistExportBridge::from_environment())
        .manage(PlaylistEvidenceExportBridge::from_environment())
        .manage(PlaylistVendorInteropBridge::from_environment())
        .manage(TransitionInspectorBridge::from_environment())
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
            playlist_editor::playlist_editor_history,
            playlist_export::playlist_export_preview,
            playlist_export::playlist_export_m3u8,
            playlist_evidence_export::playlist_evidence_preview,
            playlist_evidence_export::playlist_evidence_export_json,
            playlist_vendor_interop::playlist_vendor_interop_preview,
            playlist_vendor_interop::playlist_vendor_interop_export_rekordbox,
            transition_inspector::playlist_transition_inspect
        ])
        .run(tauri::generate_context!())
        .expect("error while running APPLAYLIST desktop host");
}
