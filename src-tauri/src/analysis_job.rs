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
    analysis_bridge::{
        AnalysisSidecarBridge, DesktopAnalysisCorrectionInput, DesktopAnalysisCountsDto,
        DesktopAnalysisInspectorItemDto, DesktopAnalysisInspectorListDto,
        SidecarAnalysisSnapshotDto,
    },
    library_capability::DesktopHostError,
};

const ANALYSIS_JOB_PREFIX: &str = "daj_";
const MAX_ANALYSIS_TRACKS: usize = 10_000;
const MAX_TRACK_ID_CHARS: usize = 256;

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct DesktopAnalysisJobSnapshotDto {
    analysis_job_id: String,
    state: String,
    counts: DesktopAnalysisCountsDto,
    terminal: bool,
    error_code: Option<String>,
}

impl DesktopAnalysisJobSnapshotDto {
    fn new(analysis_job_id: String, selected: usize) -> Self {
        Self {
            analysis_job_id,
            state: "running".to_owned(),
            counts: DesktopAnalysisCountsDto {
                selected,
                completed: 0,
                succeeded: 0,
                failed: 0,
                uncertain: 0,
            },
            terminal: false,
            error_code: None,
        }
    }
}

struct AnalysisJobRecord {
    id: Uuid,
    snapshot: Arc<Mutex<DesktopAnalysisJobSnapshotDto>>,
    cancel_requested: Arc<AtomicBool>,
}

#[derive(Default)]
pub struct AnalysisJobRegistry {
    current: Mutex<Option<AnalysisJobRecord>>,
}

enum AnalysisLaunch {
    Batch {
        track_ids: Vec<String>,
        preferred_provider: Option<String>,
    },
    Reanalysis {
        track_id: String,
        preferred_provider: Option<String>,
    },
}

impl AnalysisLaunch {
    fn selected(&self) -> usize {
        match self {
            Self::Batch { track_ids, .. } => track_ids.len(),
            Self::Reanalysis { .. } => 1,
        }
    }
}

impl AnalysisJobRegistry {
    fn start(
        &self,
        launch: AnalysisLaunch,
        bundled_resource_dir: Option<PathBuf>,
        bridge: AnalysisSidecarBridge,
    ) -> Result<DesktopAnalysisJobSnapshotDto, DesktopHostError> {
        validate_launch(&launch)?;
        let mut current = self.current.lock().map_err(|_| registry_unavailable())?;
        if let Some(existing) = current.as_ref() {
            let existing_snapshot = existing
                .snapshot
                .lock()
                .map_err(|_| registry_unavailable())?;
            if !existing_snapshot.terminal {
                return Err(analysis_already_active());
            }
        }

        let id = Uuid::new_v4();
        let encoded_id = format!("{ANALYSIS_JOB_PREFIX}{}", id.simple());
        let snapshot = Arc::new(Mutex::new(DesktopAnalysisJobSnapshotDto::new(
            encoded_id,
            launch.selected(),
        )));
        let cancel_requested = Arc::new(AtomicBool::new(false));
        *current = Some(AnalysisJobRecord {
            id,
            snapshot: Arc::clone(&snapshot),
            cancel_requested: Arc::clone(&cancel_requested),
        });
        drop(current);

        let worker_snapshot = Arc::clone(&snapshot);
        let worker_cancel = Arc::clone(&cancel_requested);
        let spawn_result = thread::Builder::new()
            .name("applaylist-analysis-job".to_owned())
            .spawn(move || {
                let progress_snapshot = Arc::clone(&worker_snapshot);
                let outcome = match launch {
                    AnalysisLaunch::Batch {
                        track_ids,
                        preferred_provider,
                    } => bridge.run_analysis_lifecycle_with_resource_dir(
                        &track_ids,
                        preferred_provider.as_deref(),
                        bundled_resource_dir.as_deref(),
                        Arc::clone(&worker_cancel),
                        move |progress| update_progress(&progress_snapshot, progress),
                    ),
                    AnalysisLaunch::Reanalysis {
                        track_id,
                        preferred_provider,
                    } => bridge.run_reanalysis_lifecycle_with_resource_dir(
                        &track_id,
                        preferred_provider.as_deref(),
                        bundled_resource_dir.as_deref(),
                        Arc::clone(&worker_cancel),
                        move |progress| update_progress(&progress_snapshot, progress),
                    ),
                };

                if let Ok(mut final_snapshot) = worker_snapshot.lock() {
                    match outcome {
                        Ok(result) => {
                            final_snapshot.state = result.status;
                            final_snapshot.counts = result.counts;
                            final_snapshot.terminal = true;
                            final_snapshot.error_code = result.error_code;
                        }
                        Err(_) => {
                            final_snapshot.state = "failed".to_owned();
                            final_snapshot.terminal = true;
                            final_snapshot.error_code = Some("desktop_analysis_failed".to_owned());
                        }
                    }
                }
            });

        if spawn_result.is_err() {
            if let Ok(mut failed_snapshot) = snapshot.lock() {
                failed_snapshot.state = "failed".to_owned();
                failed_snapshot.terminal = true;
                failed_snapshot.error_code = Some("desktop_analysis_task_failed".to_owned());
            }
            return Err(analysis_task_failed());
        }

        snapshot
            .lock()
            .map_err(|_| registry_unavailable())
            .map(|value| value.clone())
    }

    fn status(&self, raw_id: &str) -> Result<DesktopAnalysisJobSnapshotDto, DesktopHostError> {
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

    fn cancel(&self, raw_id: &str) -> Result<DesktopAnalysisJobSnapshotDto, DesktopHostError> {
        let id = parse_job_id(raw_id)?;
        let current = self.current.lock().map_err(|_| registry_unavailable())?;
        let record = current.as_ref().ok_or_else(unknown_job)?;
        if record.id != id {
            return Err(unknown_job());
        }
        let mut snapshot = record.snapshot.lock().map_err(|_| registry_unavailable())?;
        if snapshot.terminal {
            return Ok(snapshot.clone());
        }
        record.cancel_requested.store(true, Ordering::Release);
        snapshot.state = "cancelling".to_owned();
        Ok(snapshot.clone())
    }
}

fn update_progress(
    snapshot: &Arc<Mutex<DesktopAnalysisJobSnapshotDto>>,
    progress: SidecarAnalysisSnapshotDto,
) {
    let Ok(mut current) = snapshot.lock() else {
        return;
    };
    if current.terminal {
        return;
    }
    let sidecar_terminal = progress.terminal;
    if !sidecar_terminal && (current.state != "cancelling" || progress.status == "cancelling") {
        current.state = progress.status;
    }
    current.counts = progress.counts;
}

fn validate_launch(launch: &AnalysisLaunch) -> Result<(), DesktopHostError> {
    match launch {
        AnalysisLaunch::Batch {
            track_ids,
            preferred_provider,
        } => {
            if track_ids.is_empty() || track_ids.len() > MAX_ANALYSIS_TRACKS {
                return Err(invalid_analysis_request());
            }
            let mut unique = std::collections::HashSet::with_capacity(track_ids.len());
            for track_id in track_ids {
                validate_track_id(track_id)?;
                if !unique.insert(track_id) {
                    return Err(invalid_analysis_request());
                }
            }
            validate_provider(preferred_provider.as_deref())
        }
        AnalysisLaunch::Reanalysis {
            track_id,
            preferred_provider,
        } => {
            validate_track_id(track_id)?;
            validate_provider(preferred_provider.as_deref())
        }
    }
}

fn validate_track_id(track_id: &str) -> Result<(), DesktopHostError> {
    if track_id.is_empty()
        || track_id.len() > MAX_TRACK_ID_CHARS
        || track_id.trim() != track_id
        || track_id.contains('/')
        || track_id.contains('\\')
        || track_id.chars().any(char::is_control)
    {
        return Err(invalid_track_id());
    }
    Ok(())
}

fn validate_provider(provider: Option<&str>) -> Result<(), DesktopHostError> {
    if let Some(provider) = provider {
        if provider.is_empty()
            || provider.len() > 128
            || provider.trim() != provider
            || provider.chars().any(|character| !character.is_ascii_graphic())
        {
            return Err(invalid_analysis_request());
        }
    }
    Ok(())
}

fn parse_job_id(raw: &str) -> Result<Uuid, DesktopHostError> {
    let encoded = raw
        .strip_prefix(ANALYSIS_JOB_PREFIX)
        .ok_or_else(invalid_job)?;
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

fn invalid_job() -> DesktopHostError {
    DesktopHostError::new(
        "invalid_analysis_job",
        "The desktop analysis job identifier is invalid.",
    )
}

fn unknown_job() -> DesktopHostError {
    DesktopHostError::new(
        "unknown_analysis_job",
        "The desktop analysis job is not active in this session.",
    )
}

fn registry_unavailable() -> DesktopHostError {
    DesktopHostError::new(
        "analysis_job_registry_unavailable",
        "The desktop analysis job registry is temporarily unavailable.",
    )
}

fn analysis_already_active() -> DesktopHostError {
    DesktopHostError::new(
        "desktop_analysis_active",
        "A desktop analysis job is already active.",
    )
}

fn analysis_task_failed() -> DesktopHostError {
    DesktopHostError::new(
        "desktop_analysis_task_failed",
        "The desktop analysis task could not start.",
    )
}

fn invalid_analysis_request() -> DesktopHostError {
    DesktopHostError::new(
        "invalid_desktop_analysis_request",
        "The desktop analysis request is invalid.",
    )
}

fn invalid_track_id() -> DesktopHostError {
    DesktopHostError::new(
        "invalid_track_id",
        "The track identifier is invalid.",
    )
}

#[tauri::command]
pub async fn analysis_start(
    track_ids: Vec<String>,
    preferred_provider: Option<String>,
    jobs: State<'_, AnalysisJobRegistry>,
    bridge: State<'_, AnalysisSidecarBridge>,
    app: AppHandle,
) -> Result<DesktopAnalysisJobSnapshotDto, DesktopHostError> {
    let bundled_resource_dir = app.path().resource_dir().ok();
    jobs.start(
        AnalysisLaunch::Batch {
            track_ids,
            preferred_provider,
        },
        bundled_resource_dir,
        bridge.inner().clone(),
    )
}

#[tauri::command]
pub async fn analysis_reanalyze(
    track_id: String,
    preferred_provider: Option<String>,
    jobs: State<'_, AnalysisJobRegistry>,
    bridge: State<'_, AnalysisSidecarBridge>,
    app: AppHandle,
) -> Result<DesktopAnalysisJobSnapshotDto, DesktopHostError> {
    let bundled_resource_dir = app.path().resource_dir().ok();
    jobs.start(
        AnalysisLaunch::Reanalysis {
            track_id,
            preferred_provider,
        },
        bundled_resource_dir,
        bridge.inner().clone(),
    )
}

#[tauri::command]
pub async fn analysis_status(
    analysis_job_id: String,
    jobs: State<'_, AnalysisJobRegistry>,
) -> Result<DesktopAnalysisJobSnapshotDto, DesktopHostError> {
    jobs.status(&analysis_job_id)
}

#[tauri::command]
pub async fn analysis_cancel(
    analysis_job_id: String,
    jobs: State<'_, AnalysisJobRegistry>,
) -> Result<DesktopAnalysisJobSnapshotDto, DesktopHostError> {
    jobs.cancel(&analysis_job_id)
}

#[tauri::command]
pub async fn analysis_inspector_list(
    filter: String,
    bridge: State<'_, AnalysisSidecarBridge>,
    app: AppHandle,
) -> Result<DesktopAnalysisInspectorListDto, DesktopHostError> {
    let bundled_resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        bridge.inspector_list_with_resource_dir(&filter, bundled_resource_dir.as_deref())
    })
    .await
    .map_err(|_| DesktopHostError::new("desktop_analysis_task_failed", "The analysis inspector task failed."))?
    .map_err(DesktopHostError::from)
}

#[tauri::command]
pub async fn analysis_inspector_get(
    track_id: String,
    bridge: State<'_, AnalysisSidecarBridge>,
    app: AppHandle,
) -> Result<DesktopAnalysisInspectorItemDto, DesktopHostError> {
    validate_track_id(&track_id)?;
    let bundled_resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        bridge.inspector_get_with_resource_dir(&track_id, bundled_resource_dir.as_deref())
    })
    .await
    .map_err(|_| DesktopHostError::new("desktop_analysis_task_failed", "The analysis inspector task failed."))?
    .map_err(DesktopHostError::from)
}

#[tauri::command]
pub async fn analysis_correct(
    track_id: String,
    values: DesktopAnalysisCorrectionInput,
    reason: Option<String>,
    bridge: State<'_, AnalysisSidecarBridge>,
    app: AppHandle,
) -> Result<DesktopAnalysisInspectorItemDto, DesktopHostError> {
    validate_track_id(&track_id)?;
    let bundled_resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        bridge.correct_with_resource_dir(
            &track_id,
            &values,
            reason.as_deref(),
            bundled_resource_dir.as_deref(),
        )
    })
    .await
    .map_err(|_| DesktopHostError::new("desktop_analysis_task_failed", "The analysis correction task failed."))?
    .map_err(DesktopHostError::from)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record_with_state(state: &str, terminal: bool) -> (AnalysisJobRegistry, String) {
        let id = Uuid::new_v4();
        let encoded = format!("{ANALYSIS_JOB_PREFIX}{}", id.simple());
        let snapshot = DesktopAnalysisJobSnapshotDto {
            analysis_job_id: encoded.clone(),
            state: state.to_owned(),
            counts: DesktopAnalysisCountsDto {
                selected: 2,
                completed: 0,
                succeeded: 0,
                failed: 0,
                uncertain: 0,
            },
            terminal,
            error_code: None,
        };
        let registry = AnalysisJobRegistry {
            current: Mutex::new(Some(AnalysisJobRecord {
                id,
                snapshot: Arc::new(Mutex::new(snapshot)),
                cancel_requested: Arc::new(AtomicBool::new(false)),
            })),
        };
        (registry, encoded)
    }

    #[test]
    fn path_shaped_and_uppercase_desktop_job_ids_fail_closed() {
        for raw in [
            "/Users/example/job",
            "../../job",
            "daj_/tmp/job",
            "daj_ABCDEF0123456789ABCDEF0123456789",
        ] {
            assert!(parse_job_id(raw).is_err(), "{raw}");
        }
    }

    #[test]
    fn track_ids_reject_path_shapes() {
        assert!(validate_track_id("/Users/example/a.wav").is_err());
        assert!(validate_track_id(r"C:\\Users\\example\\a.wav").is_err());
        assert!(validate_track_id("aptrack:v1:sha256:abcdef").is_ok());
    }

    #[test]
    fn cancel_is_idempotent_and_terminal_state_is_immutable() {
        let (registry, id) = record_with_state("running", false);
        let first = registry.cancel(&id).expect("first cancel");
        let second = registry.cancel(&id).expect("second cancel");
        assert_eq!(first.state, "cancelling");
        assert_eq!(second.state, "cancelling");

        let (terminal_registry, terminal_id) = record_with_state("done", true);
        let terminal = terminal_registry
            .cancel(&terminal_id)
            .expect("terminal cancel remains idempotent");
        assert_eq!(terminal.state, "done");
        assert!(terminal.terminal);
    }

    #[test]
    fn terminal_sidecar_progress_is_not_published_before_atomic_final_state() {
        let id = format!("{ANALYSIS_JOB_PREFIX}{}", Uuid::new_v4().simple());
        let snapshot = Arc::new(Mutex::new(DesktopAnalysisJobSnapshotDto::new(id, 2)));
        let progress = SidecarAnalysisSnapshotDto {
            job_id: format!("aj_{}", Uuid::new_v4().simple()),
            status: "done".to_owned(),
            counts: DesktopAnalysisCountsDto {
                selected: 2,
                completed: 2,
                succeeded: 2,
                failed: 0,
                uncertain: 0,
            },
            preferred_provider: None,
            cancel_requested: false,
            error_code: None,
            error_detail: None,
            terminal: true,
        };
        update_progress(&snapshot, progress);
        let current = snapshot.lock().expect("read snapshot");
        assert_eq!(current.state, "running");
        assert_eq!(current.counts.completed, 2);
        assert!(!current.terminal);
    }
}
