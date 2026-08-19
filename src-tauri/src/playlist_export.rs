use std::{
    env,
    fs::{self, OpenOptions},
    io::{Read, Write},
    net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};
use serde_json::json;
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;
use uuid::Uuid;

use crate::library_capability::DesktopHostError;

const SIDECAR_EXECUTABLE_ENV: &str = "APPLAYLIST_DESKTOP_SIDECAR_EXECUTABLE";
const BUNDLED_SIDECAR_RESOURCE: &str = "applaylist-sidecar/applaylist-sidecar";
const PROTOCOL_VERSION: &str = "applaylist-sidecar-v1";
const SECRET_HEADER: &str = "X-APPLAYLIST-Sidecar-Secret";
const NONCE_HEADER: &str = "X-APPLAYLIST-Readiness-Nonce";
const READY_TIMEOUT: Duration = Duration::from_secs(5);
const HTTP_TIMEOUT: Duration = Duration::from_secs(30);
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_READY_BYTES: usize = 8_192;
const MAX_HTTP_RESPONSE_BYTES: u64 = 4 * 1024 * 1024;
const MAX_EXPORT_BYTES: usize = 128 * 1024;
const MAX_TOKEN: usize = 256;

#[derive(Debug, Clone)]
pub struct PlaylistExportBridge {
    executable: Option<PathBuf>,
}

impl PlaylistExportBridge {
    pub fn from_environment() -> Self {
        Self {
            executable: if cfg!(debug_assertions) {
                env::var_os(SIDECAR_EXECUTABLE_ENV).map(PathBuf::from)
            } else {
                None
            },
        }
    }

    fn executable(&self, resource_dir: Option<&Path>) -> Result<PathBuf, ExportError> {
        if let Some(path) = self.executable.as_ref() {
            let canonical = path
                .canonicalize()
                .map_err(|_| ExportError::unavailable())?;
            return canonical
                .is_file()
                .then_some(canonical)
                .ok_or_else(ExportError::unavailable);
        }
        let root = resource_dir.ok_or_else(ExportError::not_configured)?;
        let root = root
            .canonicalize()
            .map_err(|_| ExportError::unavailable())?;
        let binary = root
            .join(BUNDLED_SIDECAR_RESOURCE)
            .canonicalize()
            .map_err(|_| ExportError::unavailable())?;
        if !binary.starts_with(&root) || !binary.is_file() {
            return Err(ExportError::unavailable());
        }
        Ok(binary)
    }

    fn request(
        &self,
        path: &str,
        revision_id: &str,
        resource_dir: Option<&Path>,
    ) -> Result<Vec<u8>, ExportError> {
        let executable = self.executable(resource_dir)?;
        let mut session = Session::connect(&executable)?;
        let body = serde_json::to_vec(&json!({"revision_id": revision_id}))
            .map_err(|_| ExportError::request_failed())?;
        let response = session.post(path, &body);
        session.shutdown();
        let (status, bytes) = response?;
        if status != 200 {
            let code = serde_json::from_slice::<serde_json::Value>(&bytes)
                .ok()
                .and_then(|value| {
                    value
                        .get("error")
                        .and_then(serde_json::Value::as_str)
                        .map(str::to_owned)
                });
            return Err(ExportError::rejected(code.as_deref()));
        }
        Ok(bytes)
    }
}

impl Default for PlaylistExportBridge {
    fn default() -> Self {
        Self::from_environment()
    }
}

#[derive(Debug, Clone)]
struct ExportError {
    code: &'static str,
    message: &'static str,
}

impl ExportError {
    const fn new(code: &'static str, message: &'static str) -> Self {
        Self { code, message }
    }
    const fn not_configured() -> Self {
        Self::new(
            "desktop_playlist_export_sidecar_not_configured",
            "The playlist export service is not configured.",
        )
    }
    const fn unavailable() -> Self {
        Self::new(
            "desktop_playlist_export_sidecar_unavailable",
            "The playlist export service is unavailable.",
        )
    }
    const fn startup_failed() -> Self {
        Self::new(
            "desktop_playlist_export_sidecar_startup_failed",
            "The playlist export service could not start.",
        )
    }
    const fn readiness_failed() -> Self {
        Self::new(
            "desktop_playlist_export_sidecar_readiness_failed",
            "The playlist export service did not become ready.",
        )
    }
    const fn request_failed() -> Self {
        Self::new(
            "desktop_playlist_export_request_failed",
            "The playlist export request failed.",
        )
    }
    const fn invalid_request() -> Self {
        Self::new(
            "invalid_playlist_export_request",
            "The playlist export request is invalid.",
        )
    }
    const fn invalid_response() -> Self {
        Self::new(
            "desktop_playlist_export_response_invalid",
            "The playlist export response is invalid.",
        )
    }
    const fn invalid_target() -> Self {
        Self::new(
            "playlist_export_target_invalid",
            "The selected export target is invalid.",
        )
    }
    const fn target_exists() -> Self {
        Self::new(
            "playlist_export_target_exists",
            "The selected export target already exists; choose a new file name.",
        )
    }
    const fn write_failed() -> Self {
        Self::new(
            "playlist_export_write_failed",
            "The playlist export file could not be written.",
        )
    }
    fn rejected(code: Option<&str>) -> Self {
        match code {
            Some("playlist_export_revision_not_found") => Self::new(
                "playlist_export_revision_not_found",
                "The selected playlist revision was not found.",
            ),
            Some("playlist_export_track_missing") => Self::new(
                "playlist_export_track_missing",
                "A revision track is missing from the local track registry.",
            ),
            Some("playlist_export_track_unavailable") => Self::new(
                "playlist_export_track_unavailable",
                "A revision track file is unavailable.",
            ),
            Some("playlist_export_track_path_invalid") => Self::new(
                "playlist_export_track_path_invalid",
                "A revision track path is invalid.",
            ),
            Some("playlist_export_content_invalid") => Self::new(
                "playlist_export_content_invalid",
                "The export material contains invalid content.",
            ),
            Some("playlist_export_too_large") => Self::new(
                "playlist_export_too_large",
                "The export exceeds the bounded size limit.",
            ),
            Some("invalid_playlist_export_request") => Self::invalid_request(),
            _ => Self::new(
                "desktop_playlist_export_rejected",
                "The playlist export request was rejected.",
            ),
        }
    }
}

impl From<ExportError> for DesktopHostError {
    fn from(value: ExportError) -> Self {
        DesktopHostError::new(value.code, value.message)
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ExportSequenceItem {
    order_index: usize,
    track_id: String,
    display_name: String,
    locked: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct PlaylistExportPreview {
    schema: String,
    revision_id: String,
    playlist_id: String,
    revision_index: usize,
    format: String,
    suggested_filename: String,
    track_count: usize,
    sequence: Vec<ExportSequenceItem>,
    personal_dj_model_training_authorized: bool,
    production_activation_authorized: bool,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct PlaylistExportMaterial {
    schema: String,
    revision_id: String,
    playlist_id: String,
    revision_index: usize,
    format: String,
    suggested_filename: String,
    track_count: usize,
    content_utf8: String,
    content_sha256: String,
    byte_count: usize,
    personal_dj_model_training_authorized: bool,
    production_activation_authorized: bool,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct PlaylistExportReceipt {
    revision_id: String,
    format: String,
    filename: String,
    track_count: usize,
    content_sha256: String,
    bytes_written: usize,
    personal_dj_model_training_authorized: bool,
    production_activation_authorized: bool,
}

struct Session {
    child: Child,
    port: u16,
    secret: String,
    nonce: String,
}

impl Session {
    fn connect(executable: &Path) -> Result<Self, ExportError> {
        let secret = random_token();
        let nonce = random_token();
        let mut child = Command::new(executable)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| ExportError::startup_failed())?;
        let envelope = serde_json::to_vec(&json!({
            "protocol": PROTOCOL_VERSION,
            "secret": secret,
            "nonce": nonce
        }))
        .map_err(|_| ExportError::startup_failed())?;
        let mut stdin = child.stdin.take().ok_or_else(ExportError::startup_failed)?;
        stdin
            .write_all(&envelope)
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|_| ExportError::startup_failed())?;
        drop(stdin);
        let line = read_ready(&mut child)?;
        let ready: serde_json::Value =
            serde_json::from_slice(&line).map_err(|_| ExportError::readiness_failed())?;
        let port = validate_ready(&ready, &nonce)?;
        let (status, health) = request_json(port, "GET", "/v1/health", &secret, &nonce, None)?;
        if status != 200 {
            return Err(ExportError::readiness_failed());
        }
        let health: serde_json::Value =
            serde_json::from_slice(&health).map_err(|_| ExportError::readiness_failed())?;
        let nonce_hash = sha256_hex(nonce.as_bytes());
        if health.get("status").and_then(serde_json::Value::as_str) != Some("ready")
            || health.get("protocol").and_then(serde_json::Value::as_str) != Some(PROTOCOL_VERSION)
            || health.get("nonce_sha256").and_then(serde_json::Value::as_str)
                != Some(nonce_hash.as_str())
        {
            return Err(ExportError::readiness_failed());
        }
        Ok(Self {
            child,
            port,
            secret,
            nonce,
        })
    }

    fn post(&mut self, path: &str, body: &[u8]) -> Result<(u16, Vec<u8>), ExportError> {
        request_json(
            self.port,
            "POST",
            path,
            &self.secret,
            &self.nonce,
            Some(body),
        )
    }

    fn shutdown(&mut self) {
        let _ = request_json(
            self.port,
            "POST",
            "/v1/shutdown",
            &self.secret,
            &self.nonce,
            Some(&[]),
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

impl Drop for Session {
    fn drop(&mut self) {
        if matches!(self.child.try_wait(), Ok(None)) {
            let _ = self.child.kill();
        }
        let _ = self.child.wait();
    }
}

fn read_ready(child: &mut Child) -> Result<Vec<u8>, ExportError> {
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(ExportError::readiness_failed)?;
    let (sender, receiver) = mpsc::sync_channel(1);
    thread::spawn(move || {
        let mut line = Vec::new();
        let result = (|| -> std::io::Result<Vec<u8>> {
            for _ in 0..=MAX_READY_BYTES {
                let mut byte = [0_u8; 1];
                if stdout.read(&mut byte)? == 0 {
                    break;
                }
                if byte[0] == b'\n' {
                    return Ok(line);
                }
                line.push(byte[0]);
            }
            Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "invalid readiness line",
            ))
        })();
        let _ = sender.send(result);
    });
    receiver
        .recv_timeout(READY_TIMEOUT)
        .map_err(|_| ExportError::readiness_failed())?
        .map_err(|_| ExportError::readiness_failed())
}

fn validate_ready(value: &serde_json::Value, nonce: &str) -> Result<u16, ExportError> {
    let nonce_hash = sha256_hex(nonce.as_bytes());
    if value.get("event").and_then(serde_json::Value::as_str) != Some("ready")
        || value.get("protocol").and_then(serde_json::Value::as_str) != Some(PROTOCOL_VERSION)
        || value.get("host").and_then(serde_json::Value::as_str) != Some("127.0.0.1")
        || value.get("nonce_sha256").and_then(serde_json::Value::as_str)
            != Some(nonce_hash.as_str())
        || value
            .get("process_id")
            .and_then(serde_json::Value::as_u64)
            .unwrap_or(0)
            == 0
    {
        return Err(ExportError::readiness_failed());
    }
    value
        .get("port")
        .and_then(serde_json::Value::as_u64)
        .filter(|port| (1..=u16::MAX as u64).contains(port))
        .map(|port| port as u16)
        .ok_or_else(ExportError::readiness_failed)
}

fn request_json(
    port: u16,
    method: &str,
    path: &str,
    secret: &str,
    nonce: &str,
    body: Option<&[u8]>,
) -> Result<(u16, Vec<u8>), ExportError> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, HTTP_TIMEOUT)
        .map_err(|_| ExportError::request_failed())?;
    stream
        .set_read_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| ExportError::request_failed())?;
    stream
        .set_write_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| ExportError::request_failed())?;
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
        .map_err(|_| ExportError::request_failed())?;
    let mut response = Vec::new();
    stream
        .take(MAX_HTTP_RESPONSE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|_| ExportError::request_failed())?;
    if response.len() as u64 > MAX_HTTP_RESPONSE_BYTES {
        return Err(ExportError::request_failed());
    }
    let boundary = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(ExportError::request_failed)?;
    let headers =
        std::str::from_utf8(&response[..boundary]).map_err(|_| ExportError::request_failed())?;
    let mut lines = headers.split("\r\n");
    let mut parts = lines
        .next()
        .ok_or_else(ExportError::request_failed)?
        .split_whitespace();
    if parts.next() != Some("HTTP/1.1") {
        return Err(ExportError::request_failed());
    }
    let status = parts
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(ExportError::request_failed)?;
    let mut length = None;
    for line in lines {
        let Some((name, value)) = line.split_once(':') else {
            return Err(ExportError::request_failed());
        };
        if name.eq_ignore_ascii_case("Content-Length") {
            length = value.trim().parse::<usize>().ok();
        }
    }
    let body = &response[boundary + 4..];
    if length != Some(body.len()) {
        return Err(ExportError::request_failed());
    }
    Ok((status, body.to_vec()))
}

fn random_token() -> String {
    format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple())
}

fn sha256_hex(value: &[u8]) -> String {
    format!("{:x}", Sha256::digest(value))
}

fn token(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_TOKEN
        && value.trim() == value
        && !value.contains('/')
        && !value.contains('\\')
        && !value.chars().any(char::is_whitespace)
        && !value.chars().any(char::is_control)
}

fn display(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 512
        && value.trim() == value
        && !value.chars().any(char::is_control)
        && !value.starts_with('/')
        && !value.starts_with("\\\\")
        && !(value.len() >= 3
            && value.as_bytes()[0].is_ascii_alphabetic()
            && value.as_bytes()[1] == b':'
            && matches!(value.as_bytes()[2], b'/' | b'\\'))
}

fn safe_filename(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value.ends_with(".m3u8")
        && value.trim() == value
        && !value.contains('/')
        && !value.contains('\\')
        && !value.chars().any(char::is_control)
}

fn digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn validate_preview(value: &PlaylistExportPreview) -> Result<(), ExportError> {
    if value.schema != "applaylist-desktop-playlist-export-preview-r1"
        || !token(&value.revision_id)
        || !token(&value.playlist_id)
        || value.format != "m3u8"
        || !safe_filename(&value.suggested_filename)
        || !(3..=8).contains(&value.track_count)
        || value.track_count != value.sequence.len()
        || value.personal_dj_model_training_authorized
        || value.production_activation_authorized
    {
        return Err(ExportError::invalid_response());
    }
    for (position, item) in value.sequence.iter().enumerate() {
        if item.order_index != position || !token(&item.track_id) || !display(&item.display_name) {
            return Err(ExportError::invalid_response());
        }
    }
    Ok(())
}

fn validate_material(value: &PlaylistExportMaterial) -> Result<(), ExportError> {
    if value.schema != "applaylist-desktop-playlist-export-material-r1"
        || !token(&value.revision_id)
        || !token(&value.playlist_id)
        || value.format != "m3u8"
        || !safe_filename(&value.suggested_filename)
        || !(3..=8).contains(&value.track_count)
        || value.personal_dj_model_training_authorized
        || value.production_activation_authorized
        || value.byte_count == 0
        || value.byte_count > MAX_EXPORT_BYTES
        || value.content_utf8.as_bytes().len() != value.byte_count
        || !digest(&value.content_sha256)
        || sha256_hex(value.content_utf8.as_bytes()) != value.content_sha256
    {
        return Err(ExportError::invalid_response());
    }
    let lines: Vec<&str> = value.content_utf8.lines().collect();
    if lines.first().copied() != Some("#EXTM3U") || lines.len() != 1 + value.track_count * 2 {
        return Err(ExportError::invalid_response());
    }
    for pair in lines[1..].chunks_exact(2) {
        if !pair[0].starts_with("#EXTINF:")
            || pair[0].chars().any(char::is_control)
            || pair[1].is_empty()
            || !Path::new(pair[1]).is_absolute()
            || !Path::new(pair[1]).is_file()
            || pair[1].chars().any(char::is_control)
        {
            return Err(ExportError::invalid_response());
        }
    }
    Ok(())
}

fn normalize_target(mut target: PathBuf) -> Result<PathBuf, ExportError> {
    let extension = target.extension().and_then(|value| value.to_str());
    match extension {
        None => {
            target.set_extension("m3u8");
        }
        Some(value) if value.eq_ignore_ascii_case("m3u8") => {}
        Some(_) => return Err(ExportError::invalid_target()),
    }
    let parent = target.parent().ok_or_else(ExportError::invalid_target)?;
    if !parent.is_dir() || target.file_name().and_then(|value| value.to_str()).is_none() {
        return Err(ExportError::invalid_target());
    }
    if target.exists() {
        return Err(ExportError::target_exists());
    }
    Ok(target)
}

fn write_atomic(target: &Path, content: &[u8]) -> Result<(), ExportError> {
    let parent = target.parent().ok_or_else(ExportError::invalid_target)?;
    let temporary = parent.join(format!(
        ".applaylist-export-{}.tmp",
        Uuid::new_v4().simple()
    ));
    let result = (|| -> std::io::Result<()> {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)?;
        file.write_all(content)?;
        file.sync_all()?;
        drop(file);
        fs::rename(&temporary, target)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
        return Err(ExportError::write_failed());
    }
    Ok(())
}

async fn request_bytes(
    bridge: State<'_, PlaylistExportBridge>,
    app: &AppHandle,
    path: &'static str,
    revision_id: String,
) -> Result<Vec<u8>, DesktopHostError> {
    if !token(&revision_id) {
        return Err(ExportError::invalid_request().into());
    }
    let resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        bridge.request(path, &revision_id, resource_dir.as_deref())
    })
    .await
    .map_err(|_| {
        DesktopHostError::new(
            "desktop_playlist_export_task_failed",
            "The playlist export task failed.",
        )
    })?
    .map_err(DesktopHostError::from)
}

#[tauri::command]
pub async fn playlist_export_preview(
    revision_id: String,
    bridge: State<'_, PlaylistExportBridge>,
    app: AppHandle,
) -> Result<PlaylistExportPreview, DesktopHostError> {
    let bytes = request_bytes(
        bridge,
        &app,
        "/v1/playlist/export/preview",
        revision_id,
    )
    .await?;
    let preview: PlaylistExportPreview =
        serde_json::from_slice(&bytes).map_err(|_| ExportError::invalid_response())?;
    validate_preview(&preview).map_err(DesktopHostError::from)?;
    Ok(preview)
}

#[tauri::command]
pub async fn playlist_export_m3u8(
    revision_id: String,
    bridge: State<'_, PlaylistExportBridge>,
    app: AppHandle,
) -> Result<Option<PlaylistExportReceipt>, DesktopHostError> {
    let bytes = request_bytes(
        bridge,
        &app,
        "/v1/playlist/export/material",
        revision_id,
    )
    .await?;
    let material: PlaylistExportMaterial =
        serde_json::from_slice(&bytes).map_err(|_| ExportError::invalid_response())?;
    validate_material(&material).map_err(DesktopHostError::from)?;

    let Some(selected) = app
        .dialog()
        .file()
        .set_file_name(&material.suggested_filename)
        .add_filter("M3U8 playlist", &["m3u8"])
        .blocking_save_file()
    else {
        return Ok(None);
    };
    let selected_path = selected
        .into_path()
        .map_err(|_| DesktopHostError::from(ExportError::invalid_target()))?;
    let target = normalize_target(selected_path).map_err(DesktopHostError::from)?;
    write_atomic(&target, material.content_utf8.as_bytes()).map_err(DesktopHostError::from)?;
    let filename = target
        .file_name()
        .and_then(|value| value.to_str())
        .filter(|value| safe_filename(value))
        .ok_or_else(|| DesktopHostError::from(ExportError::invalid_target()))?
        .to_owned();

    Ok(Some(PlaylistExportReceipt {
        revision_id: material.revision_id,
        format: material.format,
        filename,
        track_count: material.track_count,
        content_sha256: material.content_sha256,
        bytes_written: material.byte_count,
        personal_dj_model_training_authorized: false,
        production_activation_authorized: false,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preview_validation_rejects_path_leakage_and_authority_escalation() {
        let valid = serde_json::from_value::<PlaylistExportPreview>(json!({
            "schema":"applaylist-desktop-playlist-export-preview-r1",
            "revision_id":"prv_abc",
            "playlist_id":"plr_abc",
            "revision_index":2,
            "format":"m3u8",
            "suggested_filename":"APPLAYLIST_prv_abc.m3u8",
            "track_count":3,
            "sequence":[
                {"order_index":0,"track_id":"track:a","display_name":"A","locked":false},
                {"order_index":1,"track_id":"track:b","display_name":"B","locked":true},
                {"order_index":2,"track_id":"track:c","display_name":"C","locked":false}
            ],
            "personal_dj_model_training_authorized":false,
            "production_activation_authorized":false
        }))
        .expect("valid preview");
        assert!(validate_preview(&valid).is_ok());

        let escalated = serde_json::from_value::<PlaylistExportPreview>(json!({
            "schema":"applaylist-desktop-playlist-export-preview-r1",
            "revision_id":"prv_abc",
            "playlist_id":"plr_abc",
            "revision_index":2,
            "format":"m3u8",
            "suggested_filename":"APPLAYLIST_prv_abc.m3u8",
            "track_count":3,
            "sequence":[
                {"order_index":0,"track_id":"track:a","display_name":"A","locked":false},
                {"order_index":1,"track_id":"track:b","display_name":"B","locked":true},
                {"order_index":2,"track_id":"track:c","display_name":"C","locked":false}
            ],
            "personal_dj_model_training_authorized":false,
            "production_activation_authorized":true
        }))
        .expect("shape valid");
        assert!(validate_preview(&escalated).is_err());

        assert!(serde_json::from_value::<PlaylistExportPreview>(json!({
            "schema":"applaylist-desktop-playlist-export-preview-r1",
            "revision_id":"prv_abc",
            "playlist_id":"plr_abc",
            "revision_index":2,
            "format":"m3u8",
            "suggested_filename":"APPLAYLIST_prv_abc.m3u8",
            "track_count":3,
            "sequence":[
                {"order_index":0,"track_id":"track:a","display_name":"A","locked":false},
                {"order_index":1,"track_id":"track:b","display_name":"B","locked":true},
                {"order_index":2,"track_id":"track:c","display_name":"C","locked":false}
            ],
            "path":"/tmp/leak.m3u8",
            "personal_dj_model_training_authorized":false,
            "production_activation_authorized":false
        }))
        .is_err());
    }

    #[test]
    fn target_normalization_enforces_m3u8_and_non_overwrite() {
        let root = std::env::temp_dir().join(format!(
            "applaylist-export-target-{}",
            Uuid::new_v4().simple()
        ));
        fs::create_dir_all(&root).expect("create target root");
        let without_extension = normalize_target(root.join("playlist")).expect("normalize target");
        assert_eq!(without_extension.extension().and_then(|v| v.to_str()), Some("m3u8"));
        assert!(normalize_target(root.join("playlist.txt")).is_err());
        fs::write(root.join("exists.m3u8"), b"existing").expect("write existing");
        assert!(normalize_target(root.join("exists.m3u8")).is_err());
        let _ = fs::remove_dir_all(root);
    }
}
