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

#[cfg(test)]
use std::ffi::OsString;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Manager, State};
use uuid::Uuid;

use crate::library_capability::{DesktopHostError, LibraryCapabilityRegistry};

const SIDECAR_EXECUTABLE_ENV: &str = "APPLAYLIST_DESKTOP_SIDECAR_EXECUTABLE";
const BUNDLED_SIDECAR_RESOURCE: &str = "applaylist-sidecar/applaylist-sidecar";
const PROTOCOL_VERSION: &str = "applaylist-sidecar-v1";
const SECRET_HEADER: &str = "X-APPLAYLIST-Sidecar-Secret";
const NONCE_HEADER: &str = "X-APPLAYLIST-Readiness-Nonce";
const READY_TIMEOUT: Duration = Duration::from_secs(5);
const HTTP_TIMEOUT: Duration = Duration::from_secs(10);
const IMPORT_TIMEOUT: Duration = Duration::from_secs(300);
const IMPORT_POLL_INTERVAL: Duration = Duration::from_millis(125);
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_READY_BYTES: usize = 8_192;
const MAX_HTTP_RESPONSE_BYTES: u64 = 32 * 1024 * 1024;

#[derive(Debug, Clone)]
pub struct SidecarBridge {
    executable: Option<PathBuf>,
}

impl SidecarBridge {
    pub fn from_environment() -> Self {
        Self {
            executable: if cfg!(debug_assertions) {
                env::var_os(SIDECAR_EXECUTABLE_ENV).map(PathBuf::from)
            } else {
                None
            },
        }
    }

    #[cfg(test)]
    pub(crate) fn for_executable(executable: OsString) -> Self {
        Self {
            executable: Some(PathBuf::from(executable)),
        }
    }

    fn configured_executable(
        &self,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<PathBuf, SidecarBridgeError> {
        if let Some(configured) = self.executable.as_ref() {
            let canonical = configured
                .canonicalize()
                .map_err(|_| SidecarBridgeError::executable_unavailable())?;
            if !canonical.is_file() {
                return Err(SidecarBridgeError::executable_unavailable());
            }
            return Ok(canonical);
        }

        let resource_dir = bundled_resource_dir.ok_or_else(SidecarBridgeError::not_configured)?;
        let canonical_resource_dir = resource_dir
            .canonicalize()
            .map_err(|_| SidecarBridgeError::executable_unavailable())?;
        let canonical = canonical_resource_dir
            .join(BUNDLED_SIDECAR_RESOURCE)
            .canonicalize()
            .map_err(|_| SidecarBridgeError::executable_unavailable())?;
        if !canonical.starts_with(&canonical_resource_dir) || !canonical.is_file() {
            return Err(SidecarBridgeError::executable_unavailable());
        }
        Ok(canonical)
    }

    #[cfg(test)]
    pub(crate) fn import_root(
        &self,
        root: &Path,
    ) -> Result<DesktopLibraryImportResultDto, SidecarBridgeError> {
        self.import_root_with_resource_dir(root, None)
    }

    fn import_root_with_resource_dir(
        &self,
        root: &Path,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<DesktopLibraryImportResultDto, SidecarBridgeError> {
        self.run_import_lifecycle_with_resource_dir(
            root,
            bundled_resource_dir,
            Arc::new(AtomicBool::new(false)),
            |_| {},
        )
    }

    pub(crate) fn run_import_lifecycle_with_resource_dir<F>(
        &self,
        root: &Path,
        bundled_resource_dir: Option<&Path>,
        cancel_requested: Arc<AtomicBool>,
        mut progress_updated: F,
    ) -> Result<DesktopLibraryImportResultDto, SidecarBridgeError>
    where
        F: FnMut(SidecarImportProgressDto),
    {
        if !root.is_absolute() || !root.is_dir() {
            return Err(SidecarBridgeError::invalid_root());
        }
        let folder = root
            .to_str()
            .ok_or_else(SidecarBridgeError::non_utf8_root)?;
        let executable = self.configured_executable(bundled_resource_dir)?;
        let secret = random_token();
        let nonce = random_token();
        let mut process = SidecarProcess::spawn(&executable, &secret, &nonce)?;
        let ready = process.read_ready()?;
        validate_ready(&ready, &nonce)?;
        verify_health(ready.port, &secret, &nonce)?;

        let request = serde_json::to_vec(&LibraryImportRequest { folder })
            .map_err(|_| SidecarBridgeError::request_encoding_failed())?;
        let (status, response) = request_json(
            ready.port,
            "POST",
            "/v1/library/import/start",
            &secret,
            &nonce,
            Some(&request),
            HTTP_TIMEOUT,
        )?;
        if status != 202 {
            return Err(SidecarBridgeError::import_rejected());
        }

        let mut lifecycle = parse_lifecycle_response(&response)?;
        progress_updated(lifecycle.progress());
        let deadline = Instant::now() + IMPORT_TIMEOUT;
        let mut cancel_sent = false;
        let mut previous_counts = lifecycle.counts.clone();

        loop {
            if lifecycle.terminal {
                let final_state = lifecycle.state.as_str();
                let result = match final_state {
                    "succeeded" | "cancelled" => lifecycle
                        .result
                        .take()
                        .ok_or_else(SidecarBridgeError::invalid_import_response)?,
                    "failed" => {
                        return Err(match lifecycle.error_code.as_deref() {
                            Some("invalid_library_root") => SidecarBridgeError::invalid_root(),
                            _ => SidecarBridgeError::import_rejected(),
                        });
                    }
                    _ => return Err(SidecarBridgeError::invalid_import_response()),
                };
                process.shutdown(ready.port, &secret, &nonce);
                return Ok(result);
            }

            if Instant::now() >= deadline {
                return Err(SidecarBridgeError::import_timeout());
            }

            if cancel_requested.load(Ordering::Acquire) && !cancel_sent {
                let (cancel_status, cancel_body) = request_json(
                    ready.port,
                    "POST",
                    "/v1/library/import/cancel",
                    &secret,
                    &nonce,
                    Some(&[]),
                    HTTP_TIMEOUT,
                )?;
                if cancel_status != 202 {
                    return Err(SidecarBridgeError::cancel_rejected());
                }
                lifecycle = parse_lifecycle_response(&cancel_body)?;
                validate_monotonic_counts(&previous_counts, &lifecycle.counts)?;
                previous_counts = lifecycle.counts.clone();
                progress_updated(lifecycle.progress());
                cancel_sent = true;
                continue;
            }

            thread::sleep(IMPORT_POLL_INTERVAL);
            let (poll_status, poll_body) = request_json(
                ready.port,
                "GET",
                "/v1/library/import/status",
                &secret,
                &nonce,
                None,
                HTTP_TIMEOUT,
            )?;
            if poll_status != 200 {
                return Err(SidecarBridgeError::request_failed());
            }
            lifecycle = parse_lifecycle_response(&poll_body)?;
            validate_monotonic_counts(&previous_counts, &lifecycle.counts)?;
            previous_counts = lifecycle.counts.clone();
            progress_updated(lifecycle.progress());
        }
    }
}

impl Default for SidecarBridge {
    fn default() -> Self {
        Self::from_environment()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SidecarBridgeError {
    code: &'static str,
    message: &'static str,
}

impl SidecarBridgeError {
    const fn not_configured() -> Self {
        Self {
            code: "desktop_sidecar_not_configured",
            message: "The desktop import service is not configured.",
        }
    }

    const fn executable_unavailable() -> Self {
        Self {
            code: "desktop_sidecar_unavailable",
            message: "The desktop import service is unavailable.",
        }
    }

    const fn invalid_root() -> Self {
        Self {
            code: "invalid_library_root",
            message: "The authorized library folder is unavailable.",
        }
    }

    const fn non_utf8_root() -> Self {
        Self {
            code: "unsupported_library_root_encoding",
            message: "The authorized library folder cannot be represented safely.",
        }
    }

    const fn startup_failed() -> Self {
        Self {
            code: "desktop_sidecar_startup_failed",
            message: "The desktop import service could not start.",
        }
    }

    const fn readiness_failed() -> Self {
        Self {
            code: "desktop_sidecar_readiness_failed",
            message: "The desktop import service did not become ready.",
        }
    }

    const fn authentication_failed() -> Self {
        Self {
            code: "desktop_sidecar_authentication_failed",
            message: "The desktop import service authentication failed.",
        }
    }

    const fn request_failed() -> Self {
        Self {
            code: "desktop_sidecar_request_failed",
            message: "The desktop import service request failed.",
        }
    }

    const fn request_encoding_failed() -> Self {
        Self {
            code: "desktop_sidecar_request_encoding_failed",
            message: "The desktop import request could not be encoded.",
        }
    }

    const fn import_rejected() -> Self {
        Self {
            code: "desktop_library_import_rejected",
            message: "The desktop library import was rejected.",
        }
    }

    const fn import_timeout() -> Self {
        Self {
            code: "desktop_library_import_timeout",
            message: "The desktop library import exceeded its bounded runtime.",
        }
    }

    const fn cancel_rejected() -> Self {
        Self {
            code: "desktop_library_import_cancel_rejected",
            message: "The desktop library import cancellation was rejected.",
        }
    }

    const fn invalid_import_response() -> Self {
        Self {
            code: "desktop_library_import_response_invalid",
            message: "The desktop library import response was invalid.",
        }
    }
}

impl From<SidecarBridgeError> for DesktopHostError {
    fn from(value: SidecarBridgeError) -> Self {
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
struct LibraryImportRequest<'a> {
    folder: &'a str,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct DesktopLibraryImportResultDto {
    pub(crate) folder_name: String,
    pub(crate) tracks: Vec<DesktopLibraryTrackDto>,
    pub(crate) issues: Vec<DesktopLibraryIssueDto>,
    pub(crate) counts: DesktopLibraryCountsDto,
    pub(crate) cancelled: bool,
    pub(crate) entry_limit_reached: bool,
    pub(crate) file_limit_reached: bool,
    pub(crate) complete: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct DesktopLibraryTrackDto {
    track_id: String,
    file_name: String,
    title: Option<String>,
    artist: Option<String>,
    album: Option<String>,
    genre: Option<String>,
    duration_seconds: Option<f64>,
    metadata_origin: String,
    relinked: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct DesktopLibraryIssueDto {
    stage: String,
    code: String,
    pub(crate) file_name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct DesktopLibraryCountsDto {
    pub(crate) discovered_entries: usize,
    pub(crate) accepted: usize,
    pub(crate) imported: usize,
    pub(crate) persisted: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SidecarImportProgressDto {
    pub(crate) state: String,
    pub(crate) phase: String,
    pub(crate) counts: DesktopLibraryCountsDto,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SidecarImportLifecycleDto {
    state: String,
    phase: String,
    counts: DesktopLibraryCountsDto,
    terminal: bool,
    result: Option<DesktopLibraryImportResultDto>,
    error_code: Option<String>,
}

impl SidecarImportLifecycleDto {
    fn progress(&self) -> SidecarImportProgressDto {
        SidecarImportProgressDto {
            state: self.state.clone(),
            phase: self.phase.clone(),
            counts: self.counts.clone(),
        }
    }
}

fn parse_lifecycle_response(body: &[u8]) -> Result<SidecarImportLifecycleDto, SidecarBridgeError> {
    let lifecycle = serde_json::from_slice::<SidecarImportLifecycleDto>(body)
        .map_err(|_| SidecarBridgeError::invalid_import_response())?;
    if !matches!(
        lifecycle.state.as_str(),
        "pending" | "running" | "cancelling" | "succeeded" | "cancelled" | "failed"
    ) || !matches!(
        lifecycle.phase.as_str(),
        "starting" | "scanning" | "importing" | "persisting" | "finalizing"
    ) {
        return Err(SidecarBridgeError::invalid_import_response());
    }
    let should_be_terminal = matches!(
        lifecycle.state.as_str(),
        "succeeded" | "cancelled" | "failed"
    );
    if lifecycle.terminal != should_be_terminal {
        return Err(SidecarBridgeError::invalid_import_response());
    }
    if lifecycle.counts.persisted > lifecycle.counts.imported
        || lifecycle.counts.imported > lifecycle.counts.accepted
        || lifecycle.counts.accepted > lifecycle.counts.discovered_entries
    {
        return Err(SidecarBridgeError::invalid_import_response());
    }
    if matches!(lifecycle.state.as_str(), "succeeded" | "cancelled")
        && lifecycle.terminal
        && lifecycle.result.is_none()
    {
        return Err(SidecarBridgeError::invalid_import_response());
    }
    Ok(lifecycle)
}

fn validate_monotonic_counts(
    previous: &DesktopLibraryCountsDto,
    next: &DesktopLibraryCountsDto,
) -> Result<(), SidecarBridgeError> {
    if next.discovered_entries < previous.discovered_entries
        || next.accepted < previous.accepted
        || next.imported < previous.imported
        || next.persisted < previous.persisted
    {
        return Err(SidecarBridgeError::invalid_import_response());
    }
    Ok(())
}

#[tauri::command]
pub async fn library_import_root(
    capability_id: String,
    registry: State<'_, LibraryCapabilityRegistry>,
    bridge: State<'_, SidecarBridge>,
    app: AppHandle,
) -> Result<DesktopLibraryImportResultDto, DesktopHostError> {
    let root = registry.resolve_for_import(&capability_id)?;
    let bundled_resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        bridge.import_root_with_resource_dir(&root, bundled_resource_dir.as_deref())
    })
    .await
    .map_err(|_| {
        DesktopHostError::new(
            "desktop_library_import_task_failed",
            "The desktop library import task failed.",
        )
    })?
    .map_err(DesktopHostError::from)
}

struct SidecarProcess {
    child: Child,
}

impl SidecarProcess {
    fn spawn(executable: &Path, secret: &str, nonce: &str) -> Result<Self, SidecarBridgeError> {
        let mut child = Command::new(executable)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| SidecarBridgeError::startup_failed())?;

        let envelope = serde_json::to_vec(&serde_json::json!({
            "protocol": PROTOCOL_VERSION,
            "secret": secret,
            "nonce": nonce,
        }))
        .map_err(|_| SidecarBridgeError::startup_failed())?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(SidecarBridgeError::startup_failed)?;
        stdin
            .write_all(&envelope)
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|_| SidecarBridgeError::startup_failed())?;
        drop(stdin);

        Ok(Self { child })
    }

    fn read_ready(&mut self) -> Result<SidecarReady, SidecarBridgeError> {
        let mut stdout = self
            .child
            .stdout
            .take()
            .ok_or_else(SidecarBridgeError::readiness_failed)?;
        let (sender, receiver) = mpsc::sync_channel(1);
        thread::spawn(move || {
            let result = read_bounded_line(&mut stdout, MAX_READY_BYTES);
            let _ = sender.send(result);
        });

        let line = receiver
            .recv_timeout(READY_TIMEOUT)
            .map_err(|_| SidecarBridgeError::readiness_failed())?
            .map_err(|_| SidecarBridgeError::readiness_failed())?;
        serde_json::from_slice(&line).map_err(|_| SidecarBridgeError::readiness_failed())
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

fn validate_ready(ready: &SidecarReady, nonce: &str) -> Result<(), SidecarBridgeError> {
    if ready.event != "ready"
        || ready.protocol != PROTOCOL_VERSION
        || ready.host != "127.0.0.1"
        || ready.port == 0
        || ready.process_id == 0
        || ready.nonce_sha256 != sha256_hex(nonce)
    {
        return Err(SidecarBridgeError::readiness_failed());
    }
    Ok(())
}

fn verify_health(port: u16, secret: &str, nonce: &str) -> Result<(), SidecarBridgeError> {
    let (status, body) =
        request_json(port, "GET", "/v1/health", secret, nonce, None, HTTP_TIMEOUT)?;
    if status == 401 {
        return Err(SidecarBridgeError::authentication_failed());
    }
    if status != 200 {
        return Err(SidecarBridgeError::request_failed());
    }
    let health = serde_json::from_slice::<HealthResponse>(&body)
        .map_err(|_| SidecarBridgeError::readiness_failed())?;
    if health.status != "ready"
        || health.protocol != PROTOCOL_VERSION
        || health.nonce_sha256 != sha256_hex(nonce)
    {
        return Err(SidecarBridgeError::readiness_failed());
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
) -> Result<(u16, Vec<u8>), SidecarBridgeError> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, HTTP_TIMEOUT)
        .map_err(|_| SidecarBridgeError::request_failed())?;
    stream
        .set_read_timeout(Some(read_timeout))
        .and_then(|_| stream.set_write_timeout(Some(HTTP_TIMEOUT)))
        .map_err(|_| SidecarBridgeError::request_failed())?;

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
        .map_err(|_| SidecarBridgeError::request_failed())?;

    let mut response = Vec::new();
    stream
        .take(MAX_HTTP_RESPONSE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|_| SidecarBridgeError::request_failed())?;
    if response.len() as u64 > MAX_HTTP_RESPONSE_BYTES {
        return Err(SidecarBridgeError::request_failed());
    }
    parse_http_response(&response)
}

fn parse_http_response(response: &[u8]) -> Result<(u16, Vec<u8>), SidecarBridgeError> {
    let boundary = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(SidecarBridgeError::request_failed)?;
    let headers = std::str::from_utf8(&response[..boundary])
        .map_err(|_| SidecarBridgeError::request_failed())?;
    let mut lines = headers.split("\r\n");
    let status_line = lines
        .next()
        .ok_or_else(SidecarBridgeError::request_failed)?;
    let mut status_parts = status_line.split_whitespace();
    if status_parts.next() != Some("HTTP/1.1") {
        return Err(SidecarBridgeError::request_failed());
    }
    let status = status_parts
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(SidecarBridgeError::request_failed)?;

    let mut content_length = None;
    for line in lines {
        let Some((name, value)) = line.split_once(':') else {
            return Err(SidecarBridgeError::request_failed());
        };
        if name.eq_ignore_ascii_case("Content-Length") {
            content_length = value.trim().parse::<usize>().ok();
        }
    }
    let body = &response[boundary + 4..];
    if content_length != Some(body.len()) {
        return Err(SidecarBridgeError::request_failed());
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
    fn renderer_import_dto_rejects_unexpected_path_fields() {
        let raw = br#"{
          "folder_name":"Music",
          "tracks":[],
          "issues":[],
          "counts":{"discovered_entries":0,"accepted":0,"imported":0,"persisted":0},
          "cancelled":false,
          "entry_limit_reached":false,
          "file_limit_reached":false,
          "complete":true,
          "absolute_path":"/Users/example/Music"
        }"#;
        assert!(serde_json::from_slice::<DesktopLibraryImportResultDto>(raw).is_err());
    }

    #[test]
    fn lifecycle_dto_rejects_path_leak_and_invalid_counter_order() {
        let leaked = br#"{
          "state":"running","phase":"scanning",
          "counts":{"discovered_entries":1,"accepted":0,"imported":0,"persisted":0},
          "terminal":false,"result":null,"error_code":null,
          "root":"/Users/example/Music"
        }"#;
        assert!(parse_lifecycle_response(leaked).is_err());

        let impossible = br#"{
          "state":"running","phase":"importing",
          "counts":{"discovered_entries":1,"accepted":0,"imported":1,"persisted":0},
          "terminal":false,"result":null,"error_code":null
        }"#;
        assert!(parse_lifecycle_response(impossible).is_err());
    }

    #[test]
    fn readiness_requires_loopback_protocol_and_nonce_binding() {
        let nonce = "n".repeat(64);
        let valid = SidecarReady {
            event: "ready".to_owned(),
            protocol: PROTOCOL_VERSION.to_owned(),
            host: "127.0.0.1".to_owned(),
            port: 49152,
            nonce_sha256: sha256_hex(&nonce),
            process_id: 123,
        };
        assert_eq!(validate_ready(&valid, &nonce), Ok(()));

        let mut wrong_host = valid;
        wrong_host.host = "0.0.0.0".to_owned();
        assert_eq!(
            validate_ready(&wrong_host, &nonce),
            Err(SidecarBridgeError::readiness_failed())
        );
    }

    #[test]
    fn http_response_parser_requires_exact_content_length() {
        let response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}";
        assert_eq!(parse_http_response(response), Ok((200, b"{}".to_vec())));

        let truncated = b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\n{}";
        assert_eq!(
            parse_http_response(truncated),
            Err(SidecarBridgeError::request_failed())
        );
    }

    #[test]
    fn bundled_resource_fallback_uses_fixed_sidecar_path() {
        let directory = TestDirectory::new("bundled-resource");
        let resource_dir = directory.path.join("Resources");
        let package_dir = resource_dir.join("applaylist-sidecar");
        std::fs::create_dir_all(&package_dir).expect("create package resource directory");
        let executable = package_dir.join("applaylist-sidecar");
        std::fs::write(&executable, b"fixture").expect("write packaged sidecar fixture");

        let bridge = SidecarBridge { executable: None };
        let resolved = bridge
            .configured_executable(Some(&resource_dir))
            .expect("resolve bundled sidecar");

        assert_eq!(
            resolved,
            executable.canonicalize().expect("canonical executable")
        );
    }

    #[test]
    fn explicit_debug_override_wins_over_bundled_resource() {
        let directory = TestDirectory::new("override-precedence");
        let resource_dir = directory.path.join("Resources");
        let package_dir = resource_dir.join("applaylist-sidecar");
        std::fs::create_dir_all(&package_dir).expect("create package resource directory");
        let bundled = package_dir.join("applaylist-sidecar");
        std::fs::write(&bundled, b"bundled").expect("write bundled fixture");

        let override_executable = directory.path.join("override-sidecar");
        std::fs::write(&override_executable, b"override").expect("write override fixture");
        let bridge = SidecarBridge::for_executable(override_executable.clone().into_os_string());

        let resolved = bridge
            .configured_executable(Some(&resource_dir))
            .expect("resolve debug override");

        assert_eq!(
            resolved,
            override_executable
                .canonicalize()
                .expect("canonical override executable")
        );
    }

    #[test]
    fn missing_bundled_resource_fails_closed() {
        let directory = TestDirectory::new("missing-resource");
        let resource_dir = directory.path.join("Resources");
        std::fs::create_dir_all(&resource_dir).expect("create empty resource directory");
        let bridge = SidecarBridge { executable: None };

        assert_eq!(
            bridge.configured_executable(Some(&resource_dir)),
            Err(SidecarBridgeError::executable_unavailable())
        );
    }

    #[cfg(unix)]
    #[test]
    fn bundled_executable_symlink_cannot_escape_resource_directory() {
        use std::os::unix::fs::symlink;

        let directory = TestDirectory::new("symlink-escape");
        let resource_dir = directory.path.join("Resources");
        let package_dir = resource_dir.join("applaylist-sidecar");
        std::fs::create_dir_all(&package_dir).expect("create package resource directory");

        let outside = directory.path.join("outside-sidecar");
        std::fs::write(&outside, b"outside").expect("write outside fixture");
        symlink(&outside, package_dir.join("applaylist-sidecar"))
            .expect("create escaping sidecar symlink");

        let bridge = SidecarBridge { executable: None };
        assert_eq!(
            bridge.configured_executable(Some(&resource_dir)),
            Err(SidecarBridgeError::executable_unavailable())
        );
    }

    struct TestDirectory {
        path: PathBuf,
    }

    impl TestDirectory {
        fn new(label: &str) -> Self {
            let path = std::env::temp_dir().join(format!(
                "applaylist-sidecar-bridge-{label}-{}",
                Uuid::new_v4().simple()
            ));
            std::fs::create_dir_all(&path).expect("create test directory");
            Self { path }
        }
    }

    impl Drop for TestDirectory {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.path);
        }
    }
}

#[cfg(test)]
mod import_timeout_regression_tests {
    use super::{request_json, HTTP_TIMEOUT, IMPORT_TIMEOUT};

    fn spawn_delayed_json_response(
        delay: std::time::Duration,
    ) -> (u16, std::thread::JoinHandle<()>) {
        let listener = std::net::TcpListener::bind(("127.0.0.1", 0))
            .expect("bind timeout regression listener");
        let port = listener
            .local_addr()
            .expect("timeout regression local addr")
            .port();

        let handle = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept timeout regression client");
            stream
                .set_read_timeout(Some(std::time::Duration::from_secs(1)))
                .expect("set timeout regression server read timeout");

            let mut request = Vec::new();
            let mut chunk = [0_u8; 1024];
            loop {
                let read = std::io::Read::read(&mut stream, &mut chunk)
                    .expect("read timeout regression request");
                if read == 0 {
                    break;
                }
                request.extend_from_slice(&chunk[..read]);
                if request.windows(4).any(|window| window == b"\r\n\r\n") {
                    break;
                }
            }

            std::thread::sleep(delay);
            let response = b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}";
            let _ = std::io::Write::write_all(&mut stream, response);
        });

        (port, handle)
    }

    #[test]
    fn request_json_respects_supplied_read_timeout_for_long_import_budget() {
        assert!(
            IMPORT_TIMEOUT > HTTP_TIMEOUT,
            "import lifecycle budget must remain longer than the control-plane timeout"
        );

        let (short_port, short_server) =
            spawn_delayed_json_response(std::time::Duration::from_millis(120));
        let short_result = request_json(
            short_port,
            "GET",
            "/timeout-regression",
            "test-secret",
            "test-nonce",
            None,
            std::time::Duration::from_millis(30),
        );
        assert!(
            short_result.is_err(),
            "short response timeout must fail before the delayed response"
        );
        short_server
            .join()
            .expect("join short timeout regression server");

        let (long_port, long_server) =
            spawn_delayed_json_response(std::time::Duration::from_millis(120));
        let (status, body) = request_json(
            long_port,
            "GET",
            "/timeout-regression",
            "test-secret",
            "test-nonce",
            None,
            std::time::Duration::from_millis(500),
        )
        .expect("long response timeout must allow the delayed response");
        assert_eq!(status, 200);
        assert_eq!(body, b"{}".to_vec());
        long_server
            .join()
            .expect("join long timeout regression server");
    }
}
