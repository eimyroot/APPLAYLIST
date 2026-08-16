use std::{
    collections::BTreeMap,
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
use serde_json::Value;
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
const ANALYSIS_TIMEOUT: Duration = Duration::from_secs(600);
const ANALYSIS_POLL_INTERVAL: Duration = Duration::from_millis(125);
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_READY_BYTES: usize = 8_192;
const MAX_HTTP_RESPONSE_BYTES: u64 = 32 * 1024 * 1024;

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

    pub(crate) fn run_analysis_lifecycle<F>(
        &self,
        track_ids: &[String],
        preferred_provider: Option<&str>,
        bundled_resource_dir: Option<&Path>,
        cancel_requested: Arc<AtomicBool>,
        progress_updated: F,
    ) -> Result<SidecarAnalysisTerminalDto, AnalysisBridgeError>
    where
        F: FnMut(SidecarAnalysisProgressDto),
    {
        let body = serde_json::to_vec(&AnalysisStartRequest {
            track_ids,
            preferred_provider,
        })
        .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        self.run_lifecycle_request(
            "/v1/analysis/start",
            &body,
            bundled_resource_dir,
            cancel_requested,
            progress_updated,
        )
    }

    pub(crate) fn run_reanalysis_lifecycle<F>(
        &self,
        track_id: &str,
        preferred_provider: Option<&str>,
        bundled_resource_dir: Option<&Path>,
        cancel_requested: Arc<AtomicBool>,
        progress_updated: F,
    ) -> Result<SidecarAnalysisTerminalDto, AnalysisBridgeError>
    where
        F: FnMut(SidecarAnalysisProgressDto),
    {
        let body = serde_json::to_vec(&AnalysisReanalyzeRequest {
            track_id,
            preferred_provider,
        })
        .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        self.run_lifecycle_request(
            "/v1/analysis/reanalyze",
            &body,
            bundled_resource_dir,
            cancel_requested,
            progress_updated,
        )
    }

    fn run_lifecycle_request<F>(
        &self,
        start_path: &str,
        start_body: &[u8],
        bundled_resource_dir: Option<&Path>,
        cancel_requested: Arc<AtomicBool>,
        mut progress_updated: F,
    ) -> Result<SidecarAnalysisTerminalDto, AnalysisBridgeError>
    where
        F: FnMut(SidecarAnalysisProgressDto),
    {
        let mut session = AnalysisSidecarSession::open(self, bundled_resource_dir)?;
        let (status, response) = session.request("POST", start_path, Some(start_body), HTTP_TIMEOUT)?;
        if status != 202 {
            return Err(AnalysisBridgeError::analysis_rejected());
        }

        let mut lifecycle = parse_analysis_job(&response)?;
        let backend_job_id = lifecycle.job_id.clone();
        progress_updated(lifecycle.progress());
        let deadline = Instant::now() + ANALYSIS_TIMEOUT;
        let mut cancel_sent = false;
        let mut previous_counts = lifecycle.counts.clone();

        loop {
            if lifecycle.terminal {
                session.shutdown();
                return Ok(lifecycle.terminal_dto());
            }
            if Instant::now() >= deadline {
                return Err(AnalysisBridgeError::analysis_timeout());
            }

            if cancel_requested.load(Ordering::Acquire) && !cancel_sent {
                let body = serde_json::to_vec(&AnalysisJobRequest {
                    job_id: &backend_job_id,
                })
                .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
                let (cancel_status, cancel_body) =
                    session.request("POST", "/v1/analysis/cancel", Some(&body), HTTP_TIMEOUT)?;
                if cancel_status != 202 {
                    return Err(AnalysisBridgeError::cancel_rejected());
                }
                lifecycle = parse_analysis_job(&cancel_body)?;
                validate_same_job(&backend_job_id, &lifecycle.job_id)?;
                validate_monotonic_counts(&previous_counts, &lifecycle.counts)?;
                previous_counts = lifecycle.counts.clone();
                progress_updated(lifecycle.progress());
                cancel_sent = true;
                continue;
            }

            thread::sleep(ANALYSIS_POLL_INTERVAL);
            let body = serde_json::to_vec(&AnalysisJobRequest {
                job_id: &backend_job_id,
            })
            .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
            let (poll_status, poll_body) =
                session.request("POST", "/v1/analysis/status", Some(&body), HTTP_TIMEOUT)?;
            if poll_status != 200 {
                return Err(AnalysisBridgeError::request_failed());
            }
            lifecycle = parse_analysis_job(&poll_body)?;
            validate_same_job(&backend_job_id, &lifecycle.job_id)?;
            validate_monotonic_counts(&previous_counts, &lifecycle.counts)?;
            previous_counts = lifecycle.counts.clone();
            progress_updated(lifecycle.progress());
        }
    }

    pub(crate) fn inspector_list(
        &self,
        filter_by: &str,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<DesktopAnalysisInspectorListDto, AnalysisBridgeError> {
        let body = serde_json::to_vec(&AnalysisInspectorListRequest { filter: filter_by })
            .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        let mut session = AnalysisSidecarSession::open(self, bundled_resource_dir)?;
        let (status, response) = session.request(
            "POST",
            "/v1/analysis/inspector/list",
            Some(&body),
            HTTP_TIMEOUT,
        )?;
        if status != 200 {
            return Err(AnalysisBridgeError::analysis_rejected());
        }
        let result = serde_json::from_slice::<DesktopAnalysisInspectorListDto>(&response)
            .map_err(|_| AnalysisBridgeError::invalid_analysis_response())?;
        validate_inspector_list(&result)?;
        session.shutdown();
        Ok(result)
    }

    pub(crate) fn inspector_get(
        &self,
        track_id: &str,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<DesktopAnalysisInspectorItemDto, AnalysisBridgeError> {
        let body = serde_json::to_vec(&AnalysisTrackRequest { track_id })
            .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        let mut session = AnalysisSidecarSession::open(self, bundled_resource_dir)?;
        let (status, response) = session.request(
            "POST",
            "/v1/analysis/inspector/get",
            Some(&body),
            HTTP_TIMEOUT,
        )?;
        if status != 200 {
            return Err(AnalysisBridgeError::analysis_rejected());
        }
        let result = serde_json::from_slice::<DesktopAnalysisInspectorItemDto>(&response)
            .map_err(|_| AnalysisBridgeError::invalid_analysis_response())?;
        validate_inspector_item(&result)?;
        session.shutdown();
        Ok(result)
    }

    pub(crate) fn correct(
        &self,
        track_id: &str,
        values: &BTreeMap<String, Value>,
        reason: Option<&str>,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<DesktopAnalysisInspectorItemDto, AnalysisBridgeError> {
        let body = serde_json::to_vec(&AnalysisCorrectionRequest {
            track_id,
            values,
            reason,
        })
        .map_err(|_| AnalysisBridgeError::request_encoding_failed())?;
        let mut session = AnalysisSidecarSession::open(self, bundled_resource_dir)?;
        let (status, response) = session.request(
            "POST",
            "/v1/analysis/correct",
            Some(&body),
            HTTP_TIMEOUT,
        )?;
        if status != 200 {
            return Err(AnalysisBridgeError::analysis_rejected());
        }
        let result = serde_json::from_slice::<DesktopAnalysisInspectorItemDto>(&response)
            .map_err(|_| AnalysisBridgeError::invalid_analysis_response())?;
        validate_inspector_item(&result)?;
        session.shutdown();
        Ok(result)
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

    const fn analysis_rejected() -> Self {
        Self {
            code: "desktop_analysis_rejected",
            message: "The desktop analysis request was rejected.",
        }
    }

    const fn analysis_timeout() -> Self {
        Self {
            code: "desktop_analysis_timeout",
            message: "The desktop analysis exceeded its bounded runtime.",
        }
    }

    const fn cancel_rejected() -> Self {
        Self {
            code: "desktop_analysis_cancel_rejected",
            message: "The desktop analysis cancellation was rejected.",
        }
    }

    const fn invalid_analysis_response() -> Self {
        Self {
            code: "desktop_analysis_response_invalid",
            message: "The desktop analysis response was invalid.",
        }
    }
}

impl From<AnalysisBridgeError> for DesktopHostError {
    fn from(value: AnalysisBridgeError) -> Self {
        DesktopHostError::new(value.code, value.message)
    }
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SidecarAnalysisProgressDto {
    pub(crate) state: String,
    pub(crate) counts: DesktopAnalysisCountsDto,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SidecarAnalysisTerminalDto {
    pub(crate) state: String,
    pub(crate) counts: DesktopAnalysisCountsDto,
    pub(crate) error_code: Option<String>,
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

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct SidecarAnalysisJobDto {
    job_id: String,
    status: String,
    counts: DesktopAnalysisCountsDto,
    preferred_provider: Option<String>,
    cancel_requested: bool,
    error_code: Option<String>,
    error_detail: Option<String>,
    terminal: bool,
}

impl SidecarAnalysisJobDto {
    fn progress(&self) -> SidecarAnalysisProgressDto {
        SidecarAnalysisProgressDto {
            state: self.status.clone(),
            counts: self.counts.clone(),
        }
    }

    fn terminal_dto(&self) -> SidecarAnalysisTerminalDto {
        SidecarAnalysisTerminalDto {
            state: self.status.clone(),
            counts: self.counts.clone(),
            error_code: self.error_code.clone(),
        }
    }
}

#[derive(Serialize)]
struct AnalysisStartRequest<'a> {
    track_ids: &'a [String],
    #[serde(skip_serializing_if = "Option::is_none")]
    preferred_provider: Option<&'a str>,
}

#[derive(Serialize)]
struct AnalysisReanalyzeRequest<'a> {
    track_id: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    preferred_provider: Option<&'a str>,
}

#[derive(Serialize)]
struct AnalysisJobRequest<'a> {
    job_id: &'a str,
}

#[derive(Serialize)]
struct AnalysisInspectorListRequest<'a> {
    filter: &'a str,
}

#[derive(Serialize)]
struct AnalysisTrackRequest<'a> {
    track_id: &'a str,
}

#[derive(Serialize)]
struct AnalysisCorrectionRequest<'a> {
    track_id: &'a str,
    values: &'a BTreeMap<String, Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    reason: Option<&'a str>,
}

fn parse_analysis_job(body: &[u8]) -> Result<SidecarAnalysisJobDto, AnalysisBridgeError> {
    let snapshot = serde_json::from_slice::<SidecarAnalysisJobDto>(body)
        .map_err(|_| AnalysisBridgeError::invalid_analysis_response())?;
    if !is_backend_job_id(&snapshot.job_id)
        || !matches!(
            snapshot.status.as_str(),
            "pending" | "running" | "cancelling" | "done" | "failed" | "cancelled"
        )
        || snapshot.terminal
            != matches!(snapshot.status.as_str(), "done" | "failed" | "cancelled")
        || snapshot.counts.completed != snapshot.counts.succeeded + snapshot.counts.failed
        || snapshot.counts.completed > snapshot.counts.selected
        || snapshot.counts.uncertain > snapshot.counts.succeeded
    {
        return Err(AnalysisBridgeError::invalid_analysis_response());
    }
    if snapshot.status == "cancelling" && !snapshot.cancel_requested {
        return Err(AnalysisBridgeError::invalid_analysis_response());
    }
    if snapshot.error_detail.as_deref().is_some_and(|value| value.len() > 512)
        || snapshot
            .preferred_provider
            .as_deref()
            .is_some_and(|value| value.len() > 128)
    {
        return Err(AnalysisBridgeError::invalid_analysis_response());
    }
    Ok(snapshot)
}

fn validate_monotonic_counts(
    previous: &DesktopAnalysisCountsDto,
    next: &DesktopAnalysisCountsDto,
) -> Result<(), AnalysisBridgeError> {
    if next.selected != previous.selected
        || next.completed < previous.completed
        || next.succeeded < previous.succeeded
        || next.failed < previous.failed
        || next.uncertain < previous.uncertain
    {
        return Err(AnalysisBridgeError::invalid_analysis_response());
    }
    Ok(())
}

fn validate_same_job(expected: &str, actual: &str) -> Result<(), AnalysisBridgeError> {
    if expected != actual {
        return Err(AnalysisBridgeError::invalid_analysis_response());
    }
    Ok(())
}

fn is_backend_job_id(value: &str) -> bool {
    value.len() == 35
        && value.starts_with("aj_")
        && value[3..].chars().all(|character| {
            character.is_ascii_hexdigit() && !character.is_ascii_uppercase()
        })
}

fn validate_inspector_list(
    value: &DesktopAnalysisInspectorListDto,
) -> Result<(), AnalysisBridgeError> {
    if !matches!(
        value.filter.as_str(),
        "all" | "uncertain" | "failed" | "corrected"
    ) {
        return Err(AnalysisBridgeError::invalid_analysis_response());
    }
    for item in &value.items {
        validate_inspector_item(item)?;
    }
    Ok(())
}

fn validate_inspector_item(value: &DesktopAnalysisInspectorItemDto) -> Result<(), AnalysisBridgeError> {
    if value.track_id.is_empty()
        || value.track_id.len() > 256
        || value.track_id.contains('/')
        || value.track_id.contains('\\')
        || value.title.is_empty()
        || value.title.len() > 1_024
        || !matches!(value.status.as_str(), "succeeded" | "failed")
        || !matches!(value.source.as_str(), "provider" | "manual-correction")
        || value.provider.is_empty()
        || value.provider.len() > 128
        || value.analysis_version.is_empty()
        || value.analysis_version.len() > 128
        || value.warnings.len() > 64
        || value.warnings.iter().any(|warning| warning.len() > 512)
    {
        return Err(AnalysisBridgeError::invalid_analysis_response());
    }
    for number in [
        value.bpm,
        value.bpm_confidence,
        value.key_confidence,
        value.energy,
        value.duration_seconds,
    ]
    .into_iter()
    .flatten()
    {
        if !number.is_finite() {
            return Err(AnalysisBridgeError::invalid_analysis_response());
        }
    }
    Ok(())
}

struct AnalysisSidecarSession {
    process: SidecarProcess,
    port: u16,
    secret: String,
    nonce: String,
}

impl AnalysisSidecarSession {
    fn open(
        bridge: &AnalysisSidecarBridge,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<Self, AnalysisBridgeError> {
        let executable = bridge.configured_executable(bundled_resource_dir)?;
        let secret = random_token();
        let nonce = random_token();
        let mut process = SidecarProcess::spawn(&executable, &secret, &nonce)?;
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

    fn request(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
        timeout: Duration,
    ) -> Result<(u16, Vec<u8>), AnalysisBridgeError> {
        request_json(
            self.port,
            method,
            path,
            &self.secret,
            &self.nonce,
            body,
            timeout,
        )
    }

    fn shutdown(&mut self) {
        self.process.shutdown(self.port, &self.secret, &self.nonce);
    }
}

struct SidecarProcess {
    child: Child,
}

impl SidecarProcess {
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

impl Drop for SidecarProcess {
    fn drop(&mut self) {
        if matches!(self.child.try_wait(), Ok(None)) {
            let _ = self.child.kill();
        }
        let _ = self.child.wait();
    }
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
    let (status, body) =
        request_json(port, "GET", "/v1/health", secret, nonce, None, HTTP_TIMEOUT)?;
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
        "analysis sidecar readiness line is missing or too large",
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn analysis_job_response_rejects_path_leak_and_invalid_counts() {
        let leaked = br#"{
          "job_id":"aj_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "status":"running",
          "counts":{"selected":2,"completed":1,"succeeded":1,"failed":0,"uncertain":0},
          "preferred_provider":"librosa","cancel_requested":false,
          "error_code":null,"error_detail":null,"terminal":false,
          "path":"/Users/example/Music/a.wav"
        }"#;
        assert!(parse_analysis_job(leaked).is_err());

        let impossible = br#"{
          "job_id":"aj_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "status":"running",
          "counts":{"selected":1,"completed":2,"succeeded":2,"failed":0,"uncertain":0},
          "preferred_provider":"librosa","cancel_requested":false,
          "error_code":null,"error_detail":null,"terminal":false
        }"#;
        assert!(parse_analysis_job(impossible).is_err());
    }

    #[test]
    fn inspector_response_rejects_absolute_path_field() {
        let raw = br#"{
          "track_id":"track-a","title":"A","artist":null,"status":"succeeded",
          "bpm":140.0,"bpm_confidence":0.9,"key_tonic":"F#","key_scale":"minor",
          "camelot":"11A","key_confidence":0.8,"energy":0.7,"duration_seconds":300.0,
          "provider":"librosa","provider_version":"0.10.2","analysis_version":"canonical-mir-v1",
          "algorithm_version":"baseline","warnings":[],"source":"provider","uncertain":false,
          "corrected":false,"attempt_evidence_id":"ae_1","effective_evidence_id":"ae_1",
          "correction_id":null,"correction_reason":null,"error_code":null,"error_detail":null,
          "absolute_path":"/Users/example/Music/a.wav"
        }"#;
        assert!(serde_json::from_slice::<DesktopAnalysisInspectorItemDto>(raw).is_err());
    }

    #[test]
    fn monotonic_counts_reject_regression() {
        let previous = DesktopAnalysisCountsDto {
            selected: 4,
            completed: 2,
            succeeded: 2,
            failed: 0,
            uncertain: 1,
        };
        let next = DesktopAnalysisCountsDto {
            selected: 4,
            completed: 1,
            succeeded: 1,
            failed: 0,
            uncertain: 0,
        };
        assert!(validate_monotonic_counts(&previous, &next).is_err());
    }
}
