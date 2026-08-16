use std::{
    env,
    io::{Read, Write},
    net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc, Arc,
    },
    thread,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::library_capability::DesktopHostError;

const SIDECAR_EXECUTABLE_ENV: &str = "APPLAYLIST_DESKTOP_SIDECAR_EXECUTABLE";
const BUNDLED_SIDECAR_RESOURCE: &str = "applaylist-sidecar/applaylist-sidecar";
const PROTOCOL_VERSION: &str = "applaylist-sidecar-v1";
const SECRET_HEADER: &str = "X-APPLAYLIST-Sidecar-Secret";
const NONCE_HEADER: &str = "X-APPLAYLIST-Readiness-Nonce";
const READY_TIMEOUT: Duration = Duration::from_secs(5);
const HTTP_TIMEOUT: Duration = Duration::from_secs(10);
const ANALYSIS_TIMEOUT: Duration = Duration::from_secs(30 * 60);
const ANALYSIS_POLL_INTERVAL: Duration = Duration::from_millis(125);
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_READY_BYTES: usize = 8_192;
const MAX_HTTP_RESPONSE_BYTES: u64 = 16 * 1024 * 1024;
const MAX_ANALYSIS_TRACKS: usize = 10_000;
const MAX_TRACK_ID_CHARS: usize = 256;

#[derive(Debug, Clone)]
pub struct AnalysisSidecarBridge {
    executable: Option<PathBuf>,
}

impl AnalysisSidecarBridge {
    pub fn from_environment() -> Self {
        Self {
            executable: if cfg!(debug_assertions) {
                env::var_os(SIDECAR_EXECUTABLE_ENV).map(PathBuf::from)
            } else {
                None
            },
        }
    }

    fn configured_executable(
        &self,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<PathBuf, AnalysisBridgeError> {
        if let Some(configured) = self.executable.as_ref() {
            let canonical = configured
                .canonicalize()
                .map_err(|_| AnalysisBridgeError::executable_unavailable())?;
            if !canonical.is_file() {
                return Err(AnalysisBridgeError::executable_unavailable());
            }
            return Ok(canonical);
        }

        let resource_dir = bundled_resource_dir.ok_or_else(AnalysisBridgeError::not_configured)?;
        let canonical_resource_dir = resource_dir
            .canonicalize()
            .map_err(|_| AnalysisBridgeError::executable_unavailable())?;
        let canonical = canonical_resource_dir
            .join(BUNDLED_SIDECAR_RESOURCE)
            .canonicalize()
            .map_err(|_| AnalysisBridgeError::executable_unavailable())?;
        if !canonical.starts_with(&canonical_resource_dir) || !canonical.is_file() {
            return Err(AnalysisBridgeError::executable_unavailable());
        }
        Ok(canonical)
    }

    pub(crate) fn run_analysis_lifecycle_with_resource_dir<F>(
        &self,
        track_ids: &[String],
        preferred_provider: Option<&str>,
        bundled_resource_dir: Option<&Path>,
        cancel_requested: Arc<AtomicBool>,
        progress_updated: F,
    ) -> Result<SidecarAnalysisSnapshotDto, AnalysisBridgeError>
    where
        F: FnMut(SidecarAnalysisSnapshotDto),
    {
        validate_track_ids(track_ids)?;
        validate_provider(preferred_provider)?;
        let request = AnalysisStartRequest {
            track_ids,
            preferred_provider,
        };
        self.run_lifecycle(
            "/v1/analysis/start",
            &request,
            bundled_resource_dir,
            cancel_requested,
            progress_updated,
        )
    }

    pub(crate) fn run_reanalysis_lifecycle_with_resource_dir<F>(
        &self,
        track_id: &str,
        preferred_provider: Option<&str>,
        bundled_resource_dir: Option<&Path>,
        cancel_requested: Arc<AtomicBool>,
        progress_updated: F,
    ) -> Result<SidecarAnalysisSnapshotDto, AnalysisBridgeError>
    where
        F: FnMut(SidecarAnalysisSnapshotDto),
    {
        validate_track_id(track_id)?;
        validate_provider(preferred_provider)?;
        let request = AnalysisReanalyzeRequest {
            track_id,
            preferred_provider,
        };
        self.run_lifecycle(
            "/v1/analysis/reanalyze",
            &request,
            bundled_resource_dir,
            cancel_requested,
            progress_updated,
        )
    }

    fn run_lifecycle<T, F>(
        &self,
        start_path: &str,
        start_request: &T,
        bundled_resource_dir: Option<&Path>,
        cancel_requested: Arc<AtomicBool>,
        mut progress_updated: F,
    ) -> Result<SidecarAnalysisSnapshotDto, AnalysisBridgeError>
    where
        T: Serialize,
        F: FnMut(SidecarAnalysisSnapshotDto),
    {
        let mut session = AuthenticatedAnalysisSession::connect(self, bundled_resource_dir)?;
        let request = serde_json::to_vec(start_request)
            .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        let (status, body) = session.post(start_path, &request)?;
        if status != 202 {
            session.shutdown();
            return Err(AnalysisBridgeError::analysis_rejected());
        }

        let mut snapshot = parse_analysis_snapshot(&body)?;
        let sidecar_job_id = snapshot.job_id.clone();
        let mut previous_counts = snapshot.counts.clone();
        progress_updated(snapshot.clone());
        let deadline = Instant::now() + ANALYSIS_TIMEOUT;
        let mut cancel_sent = false;

        loop {
            if snapshot.terminal {
                session.shutdown();
                return Ok(snapshot);
            }
            if Instant::now() >= deadline {
                session.cancel_job(&sidecar_job_id);
                session.shutdown();
                return Err(AnalysisBridgeError::analysis_timeout());
            }

            if cancel_requested.load(Ordering::Acquire) && !cancel_sent {
                let request = serde_json::to_vec(&AnalysisJobRequest {
                    job_id: &sidecar_job_id,
                })
                .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
                let response = session.post("/v1/analysis/cancel", &request);
                let (cancel_status, cancel_body) = match response {
                    Ok(value) => value,
                    Err(error) => {
                        session.cancel_job(&sidecar_job_id);
                        session.shutdown();
                        return Err(error);
                    }
                };
                if cancel_status != 202 {
                    session.cancel_job(&sidecar_job_id);
                    session.shutdown();
                    return Err(AnalysisBridgeError::cancel_rejected());
                }
                snapshot = match parse_analysis_snapshot(&cancel_body) {
                    Ok(value) => value,
                    Err(error) => {
                        session.cancel_job(&sidecar_job_id);
                        session.shutdown();
                        return Err(error);
                    }
                };
                validate_same_job(&sidecar_job_id, &snapshot)?;
                validate_monotonic_analysis_counts(&previous_counts, &snapshot.counts)?;
                previous_counts = snapshot.counts.clone();
                progress_updated(snapshot.clone());
                cancel_sent = true;
                continue;
            }

            thread::sleep(ANALYSIS_POLL_INTERVAL);
            let request = serde_json::to_vec(&AnalysisJobRequest {
                job_id: &sidecar_job_id,
            })
            .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
            let response = session.post("/v1/analysis/status", &request);
            let (poll_status, poll_body) = match response {
                Ok(value) => value,
                Err(error) => {
                    session.cancel_job(&sidecar_job_id);
                    session.shutdown();
                    return Err(error);
                }
            };
            if poll_status != 200 {
                session.cancel_job(&sidecar_job_id);
                session.shutdown();
                return Err(AnalysisBridgeError::request_failed());
            }
            snapshot = match parse_analysis_snapshot(&poll_body) {
                Ok(value) => value,
                Err(error) => {
                    session.cancel_job(&sidecar_job_id);
                    session.shutdown();
                    return Err(error);
                }
            };
            validate_same_job(&sidecar_job_id, &snapshot)?;
            validate_monotonic_analysis_counts(&previous_counts, &snapshot.counts)?;
            previous_counts = snapshot.counts.clone();
            progress_updated(snapshot.clone());
        }
    }

    pub(crate) fn inspector_list_with_resource_dir(
        &self,
        filter: &str,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<DesktopAnalysisInspectorListDto, AnalysisBridgeError> {
        if !matches!(filter, "all" | "uncertain" | "failed" | "corrected") {
            return Err(AnalysisBridgeError::invalid_inspector_request());
        }
        let request = serde_json::to_vec(&InspectorListRequest { filter })
            .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        let mut session = AuthenticatedAnalysisSession::connect(self, bundled_resource_dir)?;
        let response = session.post("/v1/analysis/inspector/list", &request);
        let result = match response {
            Ok((200, body)) => parse_inspector_list(&body),
            Ok(_) => Err(AnalysisBridgeError::inspector_rejected()),
            Err(error) => Err(error),
        };
        session.shutdown();
        result
    }

    pub(crate) fn inspector_get_with_resource_dir(
        &self,
        track_id: &str,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<DesktopAnalysisInspectorItemDto, AnalysisBridgeError> {
        validate_track_id(track_id)?;
        let request = serde_json::to_vec(&InspectorGetRequest { track_id })
            .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        let mut session = AuthenticatedAnalysisSession::connect(self, bundled_resource_dir)?;
        let response = session.post("/v1/analysis/inspector/get", &request);
        let result = match response {
            Ok((200, body)) => parse_inspector_item(&body),
            Ok((404, _)) => Err(AnalysisBridgeError::analysis_item_not_found()),
            Ok(_) => Err(AnalysisBridgeError::inspector_rejected()),
            Err(error) => Err(error),
        };
        session.shutdown();
        result
    }

    pub(crate) fn correct_with_resource_dir(
        &self,
        track_id: &str,
        values: &DesktopAnalysisCorrectionInput,
        reason: Option<&str>,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<DesktopAnalysisInspectorItemDto, AnalysisBridgeError> {
        validate_track_id(track_id)?;
        validate_correction(values, reason)?;
        let request = serde_json::to_vec(&AnalysisCorrectionRequest {
            track_id,
            values,
            reason,
        })
        .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        let mut session = AuthenticatedAnalysisSession::connect(self, bundled_resource_dir)?;
        let response = session.post("/v1/analysis/correct", &request);
        let result = match response {
            Ok((200, body)) => parse_inspector_item(&body),
            Ok(_) => Err(AnalysisBridgeError::correction_rejected()),
            Err(error) => Err(error),
        };
        session.shutdown();
        result
    }
}

impl Default for AnalysisSidecarBridge {
    fn default() -> Self {
        Self::from_environment()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct AnalysisBridgeError {
    code: &'static str,
    message: &'static str,
}

impl AnalysisBridgeError {
    const fn not_configured() -> Self {
        Self {
            code: "desktop_analysis_sidecar_not_configured",
            message: "The desktop analysis service is not configured.",
        }
    }

    const fn executable_unavailable() -> Self {
        Self {
            code: "desktop_analysis_sidecar_unavailable",
            message: "The desktop analysis service is unavailable.",
        }
    }

    const fn startup_failed() -> Self {
        Self {
            code: "desktop_analysis_sidecar_startup_failed",
            message: "The desktop analysis service could not start.",
        }
    }

    const fn readiness_failed() -> Self {
        Self {
            code: "desktop_analysis_sidecar_readiness_failed",
            message: "The desktop analysis service did not become ready.",
        }
    }

    const fn authentication_failed() -> Self {
        Self {
            code: "desktop_analysis_sidecar_authentication_failed",
            message: "The desktop analysis service authentication failed.",
        }
    }

    const fn request_failed() -> Self {
        Self {
            code: "desktop_analysis_sidecar_request_failed",
            message: "The desktop analysis service request failed.",
        }
    }

    const fn request_encoding_failed() -> Self {
        Self {
            code: "desktop_analysis_request_encoding_failed",
            message: "The desktop analysis request could not be encoded.",
        }
    }

    const fn invalid_request() -> Self {
        Self {
            code: "invalid_desktop_analysis_request",
            message: "The desktop analysis request is invalid.",
        }
    }

    const fn analysis_rejected() -> Self {
        Self {
            code: "desktop_analysis_rejected",
            message: "The desktop analysis request was rejected.",
        }
    }

    const fn analysis_timeout() -> Self {
        Self {
            code: "desktop_analysis_timeout",
            message: "The desktop analysis job exceeded its bounded runtime.",
        }
    }

    const fn cancel_rejected() -> Self {
        Self {
            code: "desktop_analysis_cancel_rejected",
            message: "The desktop analysis cancellation was rejected.",
        }
    }

    const fn invalid_response() -> Self {
        Self {
            code: "desktop_analysis_response_invalid",
            message: "The desktop analysis response was invalid.",
        }
    }

    const fn invalid_inspector_request() -> Self {
        Self {
            code: "invalid_analysis_inspector_request",
            message: "The analysis inspector request is invalid.",
        }
    }

    const fn inspector_rejected() -> Self {
        Self {
            code: "desktop_analysis_inspector_rejected",
            message: "The analysis inspector request was rejected.",
        }
    }

    const fn analysis_item_not_found() -> Self {
        Self {
            code: "desktop_analysis_item_not_found",
            message: "No analysis evidence is available for this track.",
        }
    }

    const fn correction_rejected() -> Self {
        Self {
            code: "desktop_analysis_correction_rejected",
            message: "The analysis correction was rejected.",
        }
    }
}

impl From<AnalysisBridgeError> for DesktopHostError {
    fn from(value: AnalysisBridgeError) -> Self {
        DesktopHostError::new(value.code, value.message)
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SidecarReady {
    event: String,
    protocol: String,
    host: String,
    port: u16,
    nonce_sha256: String,
    process_id: u32,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct HealthResponse {
    status: String,
    protocol: String,
    nonce_sha256: String,
}

#[derive(Debug, Serialize)]
struct AnalysisStartRequest<'a> {
    track_ids: &'a [String],
    #[serde(skip_serializing_if = "Option::is_none")]
    preferred_provider: Option<&'a str>,
}

#[derive(Debug, Serialize)]
struct AnalysisReanalyzeRequest<'a> {
    track_id: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    preferred_provider: Option<&'a str>,
}

#[derive(Debug, Serialize)]
struct AnalysisJobRequest<'a> {
    job_id: &'a str,
}

#[derive(Debug, Serialize)]
struct InspectorListRequest<'a> {
    filter: &'a str,
}

#[derive(Debug, Serialize)]
struct InspectorGetRequest<'a> {
    track_id: &'a str,
}

#[derive(Debug, Serialize)]
struct AnalysisCorrectionRequest<'a> {
    track_id: &'a str,
    values: &'a DesktopAnalysisCorrectionInput,
    #[serde(skip_serializing_if = "Option::is_none")]
    reason: Option<&'a str>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct DesktopAnalysisCountsDto {
    pub(crate) selected: usize,
    pub(crate) completed: usize,
    pub(crate) succeeded: usize,
    pub(crate) failed: usize,
    pub(crate) uncertain: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub(crate) struct SidecarAnalysisSnapshotDto {
    pub(crate) job_id: String,
    pub(crate) status: String,
    pub(crate) counts: DesktopAnalysisCountsDto,
    pub(crate) preferred_provider: Option<String>,
    pub(crate) cancel_requested: bool,
    pub(crate) error_code: Option<String>,
    pub(crate) error_detail: Option<String>,
    pub(crate) terminal: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct DesktopAnalysisInspectorItemDto {
    pub(crate) track_id: String,
    pub(crate) title: String,
    pub(crate) artist: Option<String>,
    pub(crate) status: String,
    pub(crate) bpm: Option<f64>,
    pub(crate) bpm_confidence: Option<f64>,
    pub(crate) key_tonic: Option<String>,
    pub(crate) key_scale: Option<String>,
    pub(crate) camelot: Option<String>,
    pub(crate) key_confidence: Option<f64>,
    pub(crate) energy: Option<f64>,
    pub(crate) duration_seconds: Option<f64>,
    pub(crate) provider: String,
    pub(crate) provider_version: Option<String>,
    pub(crate) analysis_version: String,
    pub(crate) algorithm_version: Option<String>,
    pub(crate) warnings: Vec<String>,
    pub(crate) source: String,
    pub(crate) uncertain: bool,
    pub(crate) corrected: bool,
    pub(crate) attempt_evidence_id: String,
    pub(crate) effective_evidence_id: Option<String>,
    pub(crate) correction_id: Option<String>,
    pub(crate) correction_reason: Option<String>,
    pub(crate) error_code: Option<String>,
    pub(crate) error_detail: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct DesktopAnalysisInspectorListDto {
    pub(crate) filter: String,
    pub(crate) items: Vec<DesktopAnalysisInspectorItemDto>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(deny_unknown_fields)]
pub struct DesktopAnalysisCorrectionInput {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bpm: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub key_tonic: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub key_scale: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub camelot: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub energy: Option<f64>,
}

struct AuthenticatedAnalysisSession {
    process: AnalysisSidecarProcess,
    port: u16,
    secret: String,
    nonce: String,
}

impl AuthenticatedAnalysisSession {
    fn connect(
        bridge: &AnalysisSidecarBridge,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<Self, AnalysisBridgeError> {
        let executable = bridge.configured_executable(bundled_resource_dir)?;
        let secret = random_token();
        let nonce = random_token();
        let mut process = AnalysisSidecarProcess::spawn(&executable, &secret, &nonce)?;
        let ready = process.read_ready()?;
        validate_ready(&ready, &nonce)?;
        verify_health(ready.port, &secret, &nonce)?;
        Ok(Self {
            process,
            port: ready.port,
            secret,
            nonce,
        })
    }

    fn post(&mut self, path: &str, body: &[u8]) -> Result<(u16, Vec<u8>), AnalysisBridgeError> {
        request_json(
            self.port,
            "POST",
            path,
            &self.secret,
            &self.nonce,
            Some(body),
            HTTP_TIMEOUT,
        )
    }

    fn cancel_job(&mut self, job_id: &str) {
        if let Ok(body) = serde_json::to_vec(&AnalysisJobRequest { job_id }) {
            let _ = self.post("/v1/analysis/cancel", &body);
        }
    }

    fn shutdown(&mut self) {
        self.process
            .shutdown(self.port, &self.secret, &self.nonce);
    }
}

struct AnalysisSidecarProcess {
    child: Child,
}

impl AnalysisSidecarProcess {
    fn spawn(executable: &Path, secret: &str, nonce: &str) -> Result<Self, AnalysisBridgeError> {
        let mut child = Command::new(executable)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| AnalysisBridgeError::startup_failed())?;
        let envelope = serde_json::to_vec(&serde_json::json!({
            "protocol": PROTOCOL_VERSION,
            "secret": secret,
            "nonce": nonce,
        }))
        .map_err(|_| AnalysisBridgeError::startup_failed())?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(AnalysisBridgeError::startup_failed)?;
        stdin
            .write_all(&envelope)
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|_| AnalysisBridgeError::startup_failed())?;
        drop(stdin);
        Ok(Self { child })
    }

    fn read_ready(&mut self) -> Result<SidecarReady, AnalysisBridgeError> {
        let mut stdout = self
            .child
            .stdout
            .take()
            .ok_or_else(AnalysisBridgeError::readiness_failed)?;
        let (sender, receiver) = mpsc::sync_channel(1);
        thread::spawn(move || {
            let result = read_bounded_line(&mut stdout, MAX_READY_BYTES);
            let _ = sender.send(result);
        });
        let line = receiver
            .recv_timeout(READY_TIMEOUT)
            .map_err(|_| AnalysisBridgeError::readiness_failed())?
            .map_err(|_| AnalysisBridgeError::readiness_failed())?;
        serde_json::from_slice(&line).map_err(|_| AnalysisBridgeError::readiness_failed())
    }

    fn shutdown(&mut self, port: u16, secret: &str, nonce: &str) {
        let _ = request_json(
            port,
            "POST",
            "/v1/shutdown",
            secret,
            nonce,
            Some(&[]),
            HTTP_TIMEOUT,
        );
        let deadline = Instant::now() + SHUTDOWN_TIMEOUT;
        while Instant::now() < deadline {
            match self.child.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) => thread::sleep(Duration::from_millis(25)),
                Err(_) => break,
            }
        }
    }
}

impl Drop for AnalysisSidecarProcess {
    fn drop(&mut self) {
        if matches!(self.child.try_wait(), Ok(None)) {
            let _ = self.child.kill();
        }
        let _ = self.child.wait();
    }
}

fn parse_analysis_snapshot(body: &[u8]) -> Result<SidecarAnalysisSnapshotDto, AnalysisBridgeError> {
    let snapshot = serde_json::from_slice::<SidecarAnalysisSnapshotDto>(body)
        .map_err(|_| AnalysisBridgeError::invalid_response())?;
    validate_sidecar_job_id(&snapshot.job_id)?;
    if !matches!(
        snapshot.status.as_str(),
        "pending" | "running" | "cancelling" | "done" | "failed" | "cancelled"
    ) {
        return Err(AnalysisBridgeError::invalid_response());
    }
    let should_be_terminal = matches!(snapshot.status.as_str(), "done" | "failed" | "cancelled");
    if snapshot.terminal != should_be_terminal
        || snapshot.counts.selected == 0
        || snapshot.counts.selected > MAX_ANALYSIS_TRACKS
        || snapshot.counts.completed != snapshot.counts.succeeded + snapshot.counts.failed
        || snapshot.counts.completed > snapshot.counts.selected
        || snapshot.counts.uncertain > snapshot.counts.succeeded
        || (snapshot.status == "done" && snapshot.counts.completed != snapshot.counts.selected)
        || (snapshot.status == "cancelling" && !snapshot.cancel_requested)
    {
        return Err(AnalysisBridgeError::invalid_response());
    }
    validate_optional_bounded_text(snapshot.preferred_provider.as_deref(), 128, false)?;
    validate_optional_bounded_text(snapshot.error_code.as_deref(), 128, false)?;
    validate_optional_bounded_text(snapshot.error_detail.as_deref(), 512, true)?;
    Ok(snapshot)
}

fn parse_inspector_list(body: &[u8]) -> Result<DesktopAnalysisInspectorListDto, AnalysisBridgeError> {
    let list = serde_json::from_slice::<DesktopAnalysisInspectorListDto>(body)
        .map_err(|_| AnalysisBridgeError::invalid_response())?;
    if !matches!(list.filter.as_str(), "all" | "uncertain" | "failed" | "corrected") {
        return Err(AnalysisBridgeError::invalid_response());
    }
    for item in &list.items {
        validate_inspector_item(item)?;
    }
    Ok(list)
}

fn parse_inspector_item(body: &[u8]) -> Result<DesktopAnalysisInspectorItemDto, AnalysisBridgeError> {
    let item = serde_json::from_slice::<DesktopAnalysisInspectorItemDto>(body)
        .map_err(|_| AnalysisBridgeError::invalid_response())?;
    validate_inspector_item(&item)?;
    Ok(item)
}

fn validate_inspector_item(item: &DesktopAnalysisInspectorItemDto) -> Result<(), AnalysisBridgeError> {
    validate_track_id(&item.track_id)?;
    if !matches!(item.status.as_str(), "succeeded" | "failed")
        || !matches!(item.source.as_str(), "provider" | "manual-correction")
        || item.title.trim().is_empty()
        || item.title.len() > 512
        || looks_like_absolute_path(&item.title)
        || item.provider.trim().is_empty()
        || item.provider.len() > 128
        || item.analysis_version.trim().is_empty()
        || item.analysis_version.len() > 128
        || item.attempt_evidence_id.trim().is_empty()
        || item.attempt_evidence_id.len() > 256
    {
        return Err(AnalysisBridgeError::invalid_response());
    }
    validate_optional_bounded_text(item.artist.as_deref(), 512, false)?;
    validate_optional_bounded_text(item.provider_version.as_deref(), 128, false)?;
    validate_optional_bounded_text(item.algorithm_version.as_deref(), 128, false)?;
    validate_optional_bounded_text(item.key_tonic.as_deref(), 32, false)?;
    validate_optional_bounded_text(item.key_scale.as_deref(), 32, false)?;
    validate_optional_bounded_text(item.camelot.as_deref(), 32, false)?;
    validate_optional_bounded_text(item.effective_evidence_id.as_deref(), 256, false)?;
    validate_optional_bounded_text(item.correction_id.as_deref(), 256, false)?;
    validate_optional_bounded_text(item.correction_reason.as_deref(), 512, false)?;
    validate_optional_bounded_text(item.error_code.as_deref(), 128, false)?;
    validate_optional_bounded_text(item.error_detail.as_deref(), 512, true)?;
    for warning in &item.warnings {
        if warning.len() > 512 || warning.chars().any(char::is_control) || looks_like_absolute_path(warning) {
            return Err(AnalysisBridgeError::invalid_response());
        }
    }
    for value in [item.bpm_confidence, item.key_confidence] {
        if let Some(value) = value {
            if !value.is_finite() || !(0.0..=1.0).contains(&value) {
                return Err(AnalysisBridgeError::invalid_response());
            }
        }
    }
    if let Some(value) = item.energy {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(AnalysisBridgeError::invalid_response());
        }
    }
    if let Some(value) = item.bpm {
        if !value.is_finite() || !(0.0..=400.0).contains(&value) {
            return Err(AnalysisBridgeError::invalid_response());
        }
    }
    if let Some(value) = item.duration_seconds {
        if !value.is_finite() || value < 0.0 {
            return Err(AnalysisBridgeError::invalid_response());
        }
    }
    Ok(())
}

fn validate_correction(
    values: &DesktopAnalysisCorrectionInput,
    reason: Option<&str>,
) -> Result<(), AnalysisBridgeError> {
    if values.bpm.is_none()
        && values.key_tonic.is_none()
        && values.key_scale.is_none()
        && values.camelot.is_none()
        && values.energy.is_none()
    {
        return Err(AnalysisBridgeError::invalid_request());
    }
    if let Some(value) = values.bpm {
        if !value.is_finite() || !(20.0..=300.0).contains(&value) {
            return Err(AnalysisBridgeError::invalid_request());
        }
    }
    if let Some(value) = values.energy {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(AnalysisBridgeError::invalid_request());
        }
    }
    for value in [
        values.key_tonic.as_deref(),
        values.key_scale.as_deref(),
        values.camelot.as_deref(),
    ] {
        validate_optional_bounded_text(value, 32, false)?;
    }
    validate_optional_bounded_text(reason, 512, true)?;
    Ok(())
}

fn validate_track_ids(track_ids: &[String]) -> Result<(), AnalysisBridgeError> {
    if track_ids.is_empty() || track_ids.len() > MAX_ANALYSIS_TRACKS {
        return Err(AnalysisBridgeError::invalid_request());
    }
    let mut unique = std::collections::HashSet::with_capacity(track_ids.len());
    for track_id in track_ids {
        validate_track_id(track_id)?;
        if !unique.insert(track_id) {
            return Err(AnalysisBridgeError::invalid_request());
        }
    }
    Ok(())
}

fn validate_track_id(track_id: &str) -> Result<(), AnalysisBridgeError> {
    if track_id.is_empty()
        || track_id.len() > MAX_TRACK_ID_CHARS
        || track_id.trim() != track_id
        || track_id.contains('/')
        || track_id.contains('\\')
        || track_id.chars().any(char::is_control)
    {
        return Err(AnalysisBridgeError::invalid_request());
    }
    Ok(())
}

fn validate_provider(provider: Option<&str>) -> Result<(), AnalysisBridgeError> {
    if let Some(provider) = provider {
        if provider.is_empty()
            || provider.len() > 128
            || provider.trim() != provider
            || provider.chars().any(|character| !character.is_ascii_graphic())
        {
            return Err(AnalysisBridgeError::invalid_request());
        }
    }
    Ok(())
}

fn validate_sidecar_job_id(job_id: &str) -> Result<(), AnalysisBridgeError> {
    let Some(encoded) = job_id.strip_prefix("aj_") else {
        return Err(AnalysisBridgeError::invalid_response());
    };
    if encoded.len() != 32
        || !encoded.chars().all(|character| character.is_ascii_hexdigit())
        || encoded.chars().any(|character| character.is_ascii_uppercase())
    {
        return Err(AnalysisBridgeError::invalid_response());
    }
    Ok(())
}

fn validate_same_job(
    expected: &str,
    snapshot: &SidecarAnalysisSnapshotDto,
) -> Result<(), AnalysisBridgeError> {
    if snapshot.job_id != expected {
        return Err(AnalysisBridgeError::invalid_response());
    }
    Ok(())
}

fn validate_monotonic_analysis_counts(
    previous: &DesktopAnalysisCountsDto,
    next: &DesktopAnalysisCountsDto,
) -> Result<(), AnalysisBridgeError> {
    if next.selected != previous.selected
        || next.completed < previous.completed
        || next.succeeded < previous.succeeded
        || next.failed < previous.failed
        || next.uncertain < previous.uncertain
    {
        return Err(AnalysisBridgeError::invalid_response());
    }
    Ok(())
}

fn validate_optional_bounded_text(
    value: Option<&str>,
    maximum: usize,
    reject_path_like: bool,
) -> Result<(), AnalysisBridgeError> {
    if let Some(value) = value {
        if value.is_empty()
            || value.len() > maximum
            || value.chars().any(char::is_control)
            || (reject_path_like && (value.contains('/') || value.contains('\\')))
        {
            return Err(AnalysisBridgeError::invalid_response());
        }
    }
    Ok(())
}

fn looks_like_absolute_path(value: &str) -> bool {
    if value.starts_with('/') || value.starts_with("\\\\") {
        return true;
    }
    let bytes = value.as_bytes();
    bytes.len() >= 3
        && bytes[1] == b':'
        && (bytes[2] == b'\\' || bytes[2] == b'/')
        && bytes[0].is_ascii_alphabetic()
}

fn random_token() -> String {
    format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple())
}

fn sha256_hex(value: &str) -> String {
    format!("{:x}", Sha256::digest(value.as_bytes()))
}

fn validate_ready(ready: &SidecarReady, nonce: &str) -> Result<(), AnalysisBridgeError> {
    if ready.event != "ready"
        || ready.protocol != PROTOCOL_VERSION
        || ready.host != "127.0.0.1"
        || ready.port == 0
        || ready.process_id == 0
        || ready.nonce_sha256 != sha256_hex(nonce)
    {
        return Err(AnalysisBridgeError::readiness_failed());
    }
    Ok(())
}

fn verify_health(port: u16, secret: &str, nonce: &str) -> Result<(), AnalysisBridgeError> {
    let (status, body) = request_json(
        port,
        "GET",
        "/v1/health",
        secret,
        nonce,
        None,
        HTTP_TIMEOUT,
    )?;
    if status == 401 {
        return Err(AnalysisBridgeError::authentication_failed());
    }
    if status != 200 {
        return Err(AnalysisBridgeError::request_failed());
    }
    let health = serde_json::from_slice::<HealthResponse>(&body)
        .map_err(|_| AnalysisBridgeError::readiness_failed())?;
    if health.status != "ready"
        || health.protocol != PROTOCOL_VERSION
        || health.nonce_sha256 != sha256_hex(nonce)
    {
        return Err(AnalysisBridgeError::readiness_failed());
    }
    Ok(())
}

fn request_json(
    port: u16,
    method: &str,
    path: &str,
    secret: &str,
    nonce: &str,
    body: Option<&[u8]>,
    read_timeout: Duration,
) -> Result<(u16, Vec<u8>), AnalysisBridgeError> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, HTTP_TIMEOUT)
        .map_err(|_| AnalysisBridgeError::request_failed())?;
    stream
        .set_read_timeout(Some(read_timeout))
        .and_then(|_| stream.set_write_timeout(Some(HTTP_TIMEOUT)))
        .map_err(|_| AnalysisBridgeError::request_failed())?;

    let payload = body.unwrap_or(&[]);
    let content_type = if body.is_some() {
        "Content-Type: application/json\r\n"
    } else {
        ""
    };
    let request = format!(
        "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n{SECRET_HEADER}: {secret}\r\n{NONCE_HEADER}: {nonce}\r\n{content_type}Content-Length: {}\r\n\r\n",
        payload.len()
    );
    stream
        .write_all(request.as_bytes())
        .and_then(|_| stream.write_all(payload))
        .and_then(|_| stream.flush())
        .map_err(|_| AnalysisBridgeError::request_failed())?;

    let mut response = Vec::new();
    stream
        .take(MAX_HTTP_RESPONSE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|_| AnalysisBridgeError::request_failed())?;
    if response.len() as u64 > MAX_HTTP_RESPONSE_BYTES {
        return Err(AnalysisBridgeError::request_failed());
    }
    parse_http_response(&response)
}

fn parse_http_response(response: &[u8]) -> Result<(u16, Vec<u8>), AnalysisBridgeError> {
    let boundary = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(AnalysisBridgeError::request_failed)?;
    let headers = std::str::from_utf8(&response[..boundary])
        .map_err(|_| AnalysisBridgeError::request_failed())?;
    let mut lines = headers.split("\r\n");
    let status_line = lines
        .next()
        .ok_or_else(AnalysisBridgeError::request_failed)?;
    let mut status_parts = status_line.split_whitespace();
    if status_parts.next() != Some("HTTP/1.1") {
        return Err(AnalysisBridgeError::request_failed());
    }
    let status = status_parts
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(AnalysisBridgeError::request_failed)?;
    let mut content_length = None;
    for line in lines {
        let Some((name, value)) = line.split_once(':') else {
            return Err(AnalysisBridgeError::request_failed());
        };
        if name.eq_ignore_ascii_case("Content-Length") {
            content_length = value.trim().parse::<usize>().ok();
        }
    }
    let body = &response[boundary + 4..];
    if content_length != Some(body.len()) {
        return Err(AnalysisBridgeError::request_failed());
    }
    Ok((status, body.to_vec()))
}

fn read_bounded_line(reader: &mut impl Read, limit: usize) -> std::io::Result<Vec<u8>> {
    let mut line = Vec::new();
    for _ in 0..=limit {
        let mut byte = [0_u8; 1];
        let count = reader.read(&mut byte)?;
        if count == 0 {
            break;
        }
        if byte[0] == b'\n' {
            return Ok(line);
        }
        line.push(byte[0]);
    }
    Err(std::io::Error::new(
        std::io::ErrorKind::InvalidData,
        "sidecar readiness line is missing or too large",
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn analysis_snapshot_rejects_path_leak_and_invalid_counts() {
        let leaked = br#"{
          "job_id":"aj_0123456789abcdef0123456789abcdef",
          "status":"failed",
          "counts":{"selected":1,"completed":0,"succeeded":0,"failed":0,"uncertain":0},
          "preferred_provider":null,
          "cancel_requested":false,
          "error_code":"analysis_failed",
          "error_detail":"/Users/example/Music/a.wav",
          "terminal":true
        }"#;
        assert!(parse_analysis_snapshot(leaked).is_err());

        let impossible = br#"{
          "job_id":"aj_0123456789abcdef0123456789abcdef",
          "status":"running",
          "counts":{"selected":1,"completed":1,"succeeded":0,"failed":0,"uncertain":0},
          "preferred_provider":null,
          "cancel_requested":false,
          "error_code":null,
          "error_detail":null,
          "terminal":false
        }"#;
        assert!(parse_analysis_snapshot(impossible).is_err());
    }

    #[test]
    fn inspector_dto_rejects_unknown_path_field() {
        let raw = br#"{
          "track_id":"track-a","title":"A","artist":null,"status":"failed",
          "bpm":null,"bpm_confidence":null,"key_tonic":null,"key_scale":null,
          "camelot":null,"key_confidence":null,"energy":null,"duration_seconds":null,
          "provider":"unknown","provider_version":null,"analysis_version":"canonical-mir-v1",
          "algorithm_version":null,"warnings":[],"source":"provider","uncertain":false,
          "corrected":false,"attempt_evidence_id":"ae_1","effective_evidence_id":null,
          "correction_id":null,"correction_reason":null,"error_code":"analysis_failed",
          "error_detail":"Analysis failed for this track.","path":"/Users/example/a.wav"
        }"#;
        assert!(parse_inspector_item(raw).is_err());
    }

    #[test]
    fn track_and_correction_inputs_fail_closed() {
        assert!(validate_track_id("/Users/example/a.wav").is_err());
        assert!(validate_track_id(r"C:\\Users\\example\\a.wav").is_err());
        let empty = DesktopAnalysisCorrectionInput::default();
        assert!(validate_correction(&empty, None).is_err());
        let valid = DesktopAnalysisCorrectionInput {
            bpm: Some(140.0),
            ..DesktopAnalysisCorrectionInput::default()
        };
        assert!(validate_correction(&valid, Some("confirmed on deck")).is_ok());
    }
}
