use std::{
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
};

use serde::Serialize;
use tauri::{AppHandle, Manager, State};
use uuid::Uuid;

use crate::{
    library_capability::{DesktopHostError, LibraryCapabilityRegistry},
    sidecar_bridge::{
        DesktopLibraryCountsDto, DesktopLibraryImportResultDto, SidecarBridge,
        SidecarImportProgressDto,
    },
};

const IMPORT_JOB_PREFIX: &str = "lij_";

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub struct DesktopImportJobSnapshotDto {
    import_job_id: String,
    state: String,
    phase: String,
    counts: DesktopLibraryCountsDto,
    terminal: bool,
    result: Option<DesktopLibraryImportResultDto>,
    error_code: Option<String>,
}

impl DesktopImportJobSnapshotDto {
    fn new(import_job_id: String) -> Self {
        Self {
            import_job_id,
            state: "running".to_owned(),
            phase: "starting".to_owned(),
            counts: empty_counts(),
            terminal: false,
            result: None,
            error_code: None,
        }
    }
}

struct ImportJobRecord {
    id: Uuid,
    snapshot: Arc<Mutex<DesktopImportJobSnapshotDto>>,
    cancel_requested: Arc<AtomicBool>,
}

#[derive(Default)]
pub struct ImportJobRegistry {
    current: Mutex<Option<ImportJobRecord>>,
}

impl ImportJobRegistry {
    fn start(
        &self,
        root: PathBuf,
        bundled_resource_dir: Option<PathBuf>,
        bridge: SidecarBridge,
    ) -> Result<DesktopImportJobSnapshotDto, DesktopHostError> {
        let mut current = self.current.lock().map_err(|_| registry_unavailable())?;
        if let Some(existing) = current.as_ref() {
            let existing_snapshot = existing
                .snapshot
                .lock()
                .map_err(|_| registry_unavailable())?;
            if !existing_snapshot.terminal {
                return Err(import_already_active());
            }
        }

        let id = Uuid::new_v4();
        let encoded_id = format!("{IMPORT_JOB_PREFIX}{}", id.simple());
        let snapshot = Arc::new(Mutex::new(DesktopImportJobSnapshotDto::new(
            encoded_id,
        )));
        let cancel_requested = Arc::new(AtomicBool::new(false));

        *current = Some(ImportJobRecord {
            id,
            snapshot: Arc::clone(&snapshot),
            cancel_requested: Arc::clone(&cancel_requested),
        });
        drop(current);

        let worker_snapshot = Arc::clone(&snapshot);
        let worker_cancel = Arc::clone(&cancel_requested);
        thread::Builder::new()
            .name("applaylist-import-job".to_owned())
            .spawn(move || {
                let progress_snapshot = Arc::clone(&worker_snapshot);
                let outcome = bridge.run_import_lifecycle_with_resource_dir(
                    &root,
                    bundled_resource_dir.as_deref(),
                    Arc::clone(&worker_cancel),
                    move |progress| update_progress(&progress_snapshot, progress),
                );

                if let Ok(mut final_snapshot) = worker_snapshot.lock() {
                    match outcome {
                        Ok(result) => {
                            final_snapshot.state = if result.cancelled {
                                "cancelled".to_owned()
                            } else {
                                "succeeded".to_owned()
                            };
                            final_snapshot.phase = "finalizing".to_owned();
                            final_snapshot.counts = result.counts.clone();
                            final_snapshot.terminal = true;
                            final_snapshot.error_code = None;
                            final_snapshot.result = Some(result);
                        }
                        Err(_) => {
                            final_snapshot.state = "failed".to_owned();
                            final_snapshot.phase = "finalizing".to_owned();
                            final_snapshot.terminal = true;
                            final_snapshot.result = None;
                            final_snapshot.error_code =
                                Some("desktop_library_import_failed".to_owned());
                        }
                    }
                }
            })
            .map_err(|_| import_task_failed())?;

        snapshot
            .lock()
            .map_err(|_| registry_unavailable())
            .map(|value| value.clone())
    }

    fn status(&self, raw_id: &str) -> Result<DesktopImportJobSnapshotDto, DesktopHostError> {
        let id = parse_job_id(raw_id)?;
        let current = self.current.lock().map_err(|_| registry_unavailable())?;
        let record = current.as_ref().ok_or_else(unknown_job)?;
        if record.id != id {
            return Err(unknown_job());
        }
        record
            .snapshot
            .lock()
            .map_err(|_| registry_unavailable())
            .map(|value| value.clone())
    }

    fn cancel(&self, raw_id: &str) -> Result<DesktopImportJobSnapshotDto, DesktopHostError> {
        let id = parse_job_id(raw_id)?;
        let current = self.current.lock().map_err(|_| registry_unavailable())?;
        let record = current.as_ref().ok_or_else(unknown_job)?;
        if record.id != id {
            return Err(unknown_job());
        }

        let mut snapshot = record
            .snapshot
            .lock()
            .map_err(|_| registry_unavailable())?;
        if snapshot.terminal {
            return Ok(snapshot.clone());
        }
        record.cancel_requested.store(true, Ordering::Release);
        snapshot.state = "cancelling".to_owned();
        Ok(snapshot.clone())
    }
}

fn update_progress(
    snapshot: &Arc<Mutex<DesktopImportJobSnapshotDto>>,
    progress: SidecarImportProgressDto,
) {
    let Ok(mut current) = snapshot.lock() else {
        return;
    };
    if current.terminal {
        return;
    }
    if current.state != "cancelling" || progress.state == "cancelling" {
        current.state = progress.state;
    }
    current.phase = progress.phase;
    current.counts = progress.counts;
}

fn parse_job_id(raw: &str) -> Result<Uuid, DesktopHostError> {
    let encoded = raw.strip_prefix(IMPORT_JOB_PREFIX).ok_or_else(invalid_job)?;
    if encoded.len() != 32
        || !encoded.chars().all(|ch| ch.is_ascii_hexdigit())
        || encoded.chars().any(|ch| ch.is_ascii_uppercase())
    {
        return Err(invalid_job());
    }
    let parsed = Uuid::parse_str(encoded).map_err(|_| invalid_job())?;
    if parsed.simple().to_string() != encoded {
        return Err(invalid_job());
    }
    Ok(parsed)
}

fn empty_counts() -> DesktopLibraryCountsDto {
    DesktopLibraryCountsDto {
        discovered_entries: 0,
        accepted: 0,
        imported: 0,
        persisted: 0,
    }
}

fn invalid_job() -> DesktopHostError {
    DesktopHostError::new(
        "invalid_import_job",
        "The desktop import job identifier is invalid.",
    )
}

fn unknown_job() -> DesktopHostError {
    DesktopHostError::new(
        "unknown_import_job",
        "The desktop import job is not active in this session.",
    )
}

fn registry_unavailable() -> DesktopHostError {
    DesktopHostError::new(
        "import_job_registry_unavailable",
        "The desktop import job registry is temporarily unavailable.",
    )
}

fn import_already_active() -> DesktopHostError {
    DesktopHostError::new(
        "desktop_library_import_active",
        "A desktop library import is already active.",
    )
}

fn import_task_failed() -> DesktopHostError {
    DesktopHostError::new(
        "desktop_library_import_task_failed",
        "The desktop library import task could not start.",
    )
}

#[tauri::command]
pub async fn library_import_start(
    capability_id: String,
    registry: State<'_, LibraryCapabilityRegistry>,
    jobs: State<'_, ImportJobRegistry>,
    bridge: State<'_, SidecarBridge>,
    app: AppHandle,
) -> Result<DesktopImportJobSnapshotDto, DesktopHostError> {
    let root = registry.resolve_for_import(&capability_id)?;
    let bundled_resource_dir = app.path().resource_dir().ok();
    jobs.start(root, bundled_resource_dir, bridge.inner().clone())
}

#[tauri::command]
pub async fn library_import_status(
    import_job_id: String,
    jobs: State<'_, ImportJobRegistry>,
) -> Result<DesktopImportJobSnapshotDto, DesktopHostError> {
    jobs.status(&import_job_id)
}

#[tauri::command]
pub async fn library_import_cancel(
    import_job_id: String,
    jobs: State<'_, ImportJobRegistry>,
) -> Result<DesktopImportJobSnapshotDto, DesktopHostError> {
    jobs.cancel(&import_job_id)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record_with_state(state: &str, terminal: bool) -> (ImportJobRegistry, String) {
        let id = Uuid::new_v4();
        let encoded = format!("{IMPORT_JOB_PREFIX}{}", id.simple());
        let snapshot = DesktopImportJobSnapshotDto {
            import_job_id: encoded.clone(),
            state: state.to_owned(),
            phase: "scanning".to_owned(),
            counts: empty_counts(),
            terminal,
            result: None,
            error_code: None,
        };
        let registry = ImportJobRegistry {
            current: Mutex::new(Some(ImportJobRecord {
                id,
                snapshot: Arc::new(Mutex::new(snapshot)),
                cancel_requested: Arc::new(AtomicBool::new(false)),
            })),
        };
        (registry, encoded)
    }

    #[test]
    fn path_shaped_and_uppercase_job_ids_fail_closed() {
        for raw in [
            "/Users/example/job",
            "../../job",
            "lij_/tmp/job",
            "lij_ABCDEF0123456789ABCDEF0123456789",
        ] {
            assert!(parse_job_id(raw).is_err(), "{raw}");
        }
    }

    #[test]
    fn unknown_well_formed_job_id_is_rejected() {
        let registry = ImportJobRegistry::default();
        let raw = format!("{IMPORT_JOB_PREFIX}{}", Uuid::new_v4().simple());
        assert!(registry.status(&raw).is_err());
        assert!(registry.cancel(&raw).is_err());
    }

    #[test]
    fn cancel_is_idempotent_for_active_job() {
        let (registry, id) = record_with_state("running", false);

        let first = registry.cancel(&id).expect("first cancel");
        let second = registry.cancel(&id).expect("second cancel");

        assert_eq!(first.state, "cancelling");
        assert_eq!(second.state, "cancelling");
        assert!(!second.terminal);
    }

    #[test]
    fn cancel_does_not_rewrite_terminal_state() {
        let (registry, id) = record_with_state("succeeded", true);
        let snapshot = registry.cancel(&id).expect("terminal cancel is idempotent");
        assert_eq!(snapshot.state, "succeeded");
        assert!(snapshot.terminal);
    }
}