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
const MAX_XML_BYTES: usize = 128 * 1024;
const MAX_TOKEN: usize = 256;

#[derive(Debug, Clone)]
pub struct PlaylistVendorInteropBridge {
    executable: Option<PathBuf>,
}

impl PlaylistVendorInteropBridge {
    pub fn from_environment() -> Self {
        Self {
            executable: if cfg!(debug_assertions) {
                env::var_os(SIDECAR_EXECUTABLE_ENV).map(PathBuf::from)
            } else {
                None
            },
        }
    }

    fn executable(&self, resource_dir: Option<&Path>) -> Result<PathBuf, VendorInteropError> {
        if let Some(path) = self.executable.as_ref() {
            let canonical = path
                .canonicalize()
                .map_err(|_| VendorInteropError::unavailable())?;
            return canonical
                .is_file()
                .then_some(canonical)
                .ok_or_else(VendorInteropError::unavailable);
        }
        let root = resource_dir.ok_or_else(VendorInteropError::not_configured)?;
        let root = root
            .canonicalize()
            .map_err(|_| VendorInteropError::unavailable())?;
        let binary = root
            .join(BUNDLED_SIDECAR_RESOURCE)
            .canonicalize()
            .map_err(|_| VendorInteropError::unavailable())?;
        if !binary.starts_with(&root) || !binary.is_file() {
            return Err(VendorInteropError::unavailable());
        }
        Ok(binary)
    }

    fn request(
        &self,
        path: &str,
        revision_id: &str,
        resource_dir: Option<&Path>,
    ) -> Result<Vec<u8>, VendorInteropError> {
        let executable = self.executable(resource_dir)?;
        let mut session = Session::connect(&executable)?;
        let body = serde_json::to_vec(&json!({"revision_id": revision_id}))
            .map_err(|_| VendorInteropError::request_failed())?;
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
            return Err(VendorInteropError::rejected(code.as_deref()));
        }
        Ok(bytes)
    }
}

impl Default for PlaylistVendorInteropBridge {
    fn default() -> Self {
        Self::from_environment()
    }
}

#[derive(Debug, Clone)]
struct VendorInteropError {
    code: &'static str,
    message: &'static str,
}

impl VendorInteropError {
    const fn new(code: &'static str, message: &'static str) -> Self {
        Self { code, message }
    }
    const fn not_configured() -> Self {
        Self::new(
            "desktop_vendor_interop_sidecar_not_configured",
            "The vendor interoperability service is not configured.",
        )
    }
    const fn unavailable() -> Self {
        Self::new(
            "desktop_vendor_interop_sidecar_unavailable",
            "The vendor interoperability service is unavailable.",
        )
    }
    const fn startup_failed() -> Self {
        Self::new(
            "desktop_vendor_interop_sidecar_startup_failed",
            "The vendor interoperability service could not start.",
        )
    }
    const fn readiness_failed() -> Self {
        Self::new(
            "desktop_vendor_interop_sidecar_readiness_failed",
            "The vendor interoperability service did not become ready.",
        )
    }
    const fn request_failed() -> Self {
        Self::new(
            "desktop_vendor_interop_request_failed",
            "The vendor interoperability request failed.",
        )
    }
    const fn invalid_request() -> Self {
        Self::new(
            "invalid_playlist_vendor_interop_request",
            "The vendor interoperability request is invalid.",
        )
    }
    const fn invalid_response() -> Self {
        Self::new(
            "desktop_vendor_interop_response_invalid",
            "The vendor interoperability response is invalid.",
        )
    }
    const fn invalid_target() -> Self {
        Self::new(
            "vendor_interop_target_invalid",
            "The selected vendor export target is invalid.",
        )
    }
    const fn target_exists() -> Self {
        Self::new(
            "vendor_interop_target_exists",
            "The selected vendor export target already exists; choose a new file name.",
        )
    }
    const fn write_failed() -> Self {
        Self::new(
            "vendor_interop_write_failed",
            "The vendor export file could not be written.",
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
            Some("playlist_export_track_path_invalid") | Some("vendor_interop_path_invalid") => {
                Self::new(
                    "vendor_interop_path_invalid",
                    "A revision track path is invalid for vendor handoff.",
                )
            }
            Some("playlist_export_content_invalid") => Self::new(
                "playlist_export_content_invalid",
                "The canonical export material contains invalid content.",
            ),
            Some("vendor_interop_export_too_large") => Self::new(
                "vendor_interop_export_too_large",
                "The vendor export exceeds the bounded size limit.",
            ),
            Some("invalid_playlist_vendor_interop_request") => Self::invalid_request(),
            _ => Self::new(
                "desktop_vendor_interop_rejected",
                "The vendor interoperability request was rejected.",
            ),
        }
    }
}

impl From<VendorInteropError> for DesktopHostError {
    fn from(value: VendorInteropError) -> Self {
        DesktopHostError::new(value.code, value.message)
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct VendorCapability {
    vendor: String,
    status: String,
    artifact_format: Option<String>,
    source_reference_code: String,
    user_action_code: String,
    artifact_export_available: bool,
    vendor_database_mutation_authorized: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct VendorInteropPreview {
    schema: String,
    catalog_version: String,
    verified_at: String,
    revision_id: String,
    playlist_id: String,
    revision_index: usize,
    track_count: usize,
    m3u8_path_valid: bool,
    m3u8_content_sha256: String,
    capabilities: Vec<VendorCapability>,
    personal_dj_model_training_authorized: bool,
    production_activation_authorized: bool,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct RekordboxMaterial {
    schema: String,
    vendor: String,
    format: String,
    revision_id: String,
    playlist_id: String,
    revision_index: usize,
    suggested_filename: String,
    track_count: usize,
    content_utf8: String,
    content_sha256: String,
    byte_count: usize,
    m3u8_content_sha256: String,
    vendor_database_mutation_authorized: bool,
    personal_dj_model_training_authorized: bool,
    production_activation_authorized: bool,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct VendorInteropReceipt {
    revision_id: String,
    vendor: String,
    format: String,
    filename: String,
    track_count: usize,
    content_sha256: String,
    bytes_written: usize,
    m3u8_content_sha256: String,
    vendor_database_mutation_authorized: bool,
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
    fn connect(executable: &Path) -> Result<Self, VendorInteropError> {
        let secret = random_token();
        let nonce = random_token();
        let mut child = Command::new(executable)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| VendorInteropError::startup_failed())?;
        let envelope = serde_json::to_vec(&json!({
            "protocol": PROTOCOL_VERSION,
            "secret": secret,
            "nonce": nonce
        }))
        .map_err(|_| VendorInteropError::startup_failed())?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(VendorInteropError::startup_failed)?;
        stdin
            .write_all(&envelope)
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|_| VendorInteropError::startup_failed())?;
        drop(stdin);
        let line = read_ready(&mut child)?;
        let ready: serde_json::Value =
            serde_json::from_slice(&line).map_err(|_| VendorInteropError::readiness_failed())?;
        let port = validate_ready(&ready, &nonce)?;
        let (status, health) = request_json(port, "GET", "/v1/health", &secret, &nonce, None)?;
        if status != 200 {
            return Err(VendorInteropError::readiness_failed());
        }
        let health: serde_json::Value =
            serde_json::from_slice(&health).map_err(|_| VendorInteropError::readiness_failed())?;
        let nonce_hash = sha256_hex(nonce.as_bytes());
        if health.get("status").and_then(serde_json::Value::as_str) != Some("ready")
            || health.get("protocol").and_then(serde_json::Value::as_str) != Some(PROTOCOL_VERSION)
            || health
                .get("nonce_sha256")
                .and_then(serde_json::Value::as_str)
                != Some(nonce_hash.as_str())
        {
            return Err(VendorInteropError::readiness_failed());
        }
        Ok(Self {
            child,
            port,
            secret,
            nonce,
        })
    }

    fn post(&mut self, path: &str, body: &[u8]) -> Result<(u16, Vec<u8>), VendorInteropError> {
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

fn read_ready(child: &mut Child) -> Result<Vec<u8>, VendorInteropError> {
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(VendorInteropError::readiness_failed)?;
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
        .map_err(|_| VendorInteropError::readiness_failed())?
        .map_err(|_| VendorInteropError::readiness_failed())
}

fn validate_ready(value: &serde_json::Value, nonce: &str) -> Result<u16, VendorInteropError> {
    let nonce_hash = sha256_hex(nonce.as_bytes());
    if value.get("event").and_then(serde_json::Value::as_str) != Some("ready")
        || value.get("protocol").and_then(serde_json::Value::as_str) != Some(PROTOCOL_VERSION)
        || value.get("host").and_then(serde_json::Value::as_str) != Some("127.0.0.1")
        || value
            .get("nonce_sha256")
            .and_then(serde_json::Value::as_str)
            != Some(nonce_hash.as_str())
        || value
            .get("process_id")
            .and_then(serde_json::Value::as_u64)
            .unwrap_or(0)
            == 0
    {
        return Err(VendorInteropError::readiness_failed());
    }
    value
        .get("port")
        .and_then(serde_json::Value::as_u64)
        .filter(|port| (1..=u16::MAX as u64).contains(port))
        .map(|port| port as u16)
        .ok_or_else(VendorInteropError::readiness_failed)
}

fn request_json(
    port: u16,
    method: &str,
    path: &str,
    secret: &str,
    nonce: &str,
    body: Option<&[u8]>,
) -> Result<(u16, Vec<u8>), VendorInteropError> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, HTTP_TIMEOUT)
        .map_err(|_| VendorInteropError::request_failed())?;
    stream
        .set_read_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| VendorInteropError::request_failed())?;
    stream
        .set_write_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| VendorInteropError::request_failed())?;
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
        .map_err(|_| VendorInteropError::request_failed())?;
    let mut response = Vec::new();
    stream
        .take(MAX_HTTP_RESPONSE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|_| VendorInteropError::request_failed())?;
    if response.len() as u64 > MAX_HTTP_RESPONSE_BYTES {
        return Err(VendorInteropError::request_failed());
    }
    let boundary = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(VendorInteropError::request_failed)?;
    let headers =
        std::str::from_utf8(&response[..boundary]).map_err(|_| VendorInteropError::request_failed())?;
    let mut lines = headers.split("\r\n");
    let mut parts = lines
        .next()
        .ok_or_else(VendorInteropError::request_failed)?
        .split_whitespace();
    if parts.next() != Some("HTTP/1.1") {
        return Err(VendorInteropError::request_failed());
    }
    let status = parts
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(VendorInteropError::request_failed)?;
    let mut length = None;
    for line in lines {
        let Some((name, value)) = line.split_once(':') else {
            return Err(VendorInteropError::request_failed());
        };
        if name.eq_ignore_ascii_case("Content-Length") {
            length = value.trim().parse::<usize>().ok();
        }
    }
    let body = &response[boundary + 4..];
    if length != Some(body.len()) {
        return Err(VendorInteropError::request_failed());
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

fn digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn safe_xml_filename(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value.ends_with(".xml")
        && value.trim() == value
        && !value.contains('/')
        && !value.contains('\\')
        && !value.chars().any(char::is_control)
}

fn validate_preview(value: &VendorInteropPreview) -> Result<(), VendorInteropError> {
    if value.schema != "applaylist-desktop-vendor-interop-preview-r1"
        || value.catalog_version != "vendor-interop-catalog-r1"
        || value.verified_at != "2026-08-19"
        || !token(&value.revision_id)
        || !token(&value.playlist_id)
        || !(3..=8).contains(&value.track_count)
        || !value.m3u8_path_valid
        || !digest(&value.m3u8_content_sha256)
        || value.capabilities.len() != 3
        || value.personal_dj_model_training_authorized
        || value.production_activation_authorized
    {
        return Err(VendorInteropError::invalid_response());
    }
    let expected = [
        (
            "rekordbox",
            "documented_format_export",
            Some("rekordbox_xml"),
            "rekordbox_xml_bridge_official",
            "import_xml_via_bridge",
            true,
        ),
        (
            "traktor",
            "guidance_only_nml_required",
            None,
            "traktor_nml_import_official",
            "use_supported_nml_import_workflow",
            false,
        ),
        (
            "serato",
            "guidance_only_files_crate",
            None,
            "serato_files_crate_official",
            "drag_files_or_folder_to_crate",
            false,
        ),
    ];
    for (capability, expected) in value.capabilities.iter().zip(expected) {
        if capability.vendor != expected.0
            || capability.status != expected.1
            || capability.artifact_format.as_deref() != expected.2
            || capability.source_reference_code != expected.3
            || capability.user_action_code != expected.4
            || capability.artifact_export_available != expected.5
            || capability.vendor_database_mutation_authorized
        {
            return Err(VendorInteropError::invalid_response());
        }
    }
    Ok(())
}

fn validate_material(value: &RekordboxMaterial) -> Result<(), VendorInteropError> {
    if value.schema != "applaylist-desktop-vendor-interop-material-r1"
        || value.vendor != "rekordbox"
        || value.format != "rekordbox_xml"
        || !token(&value.revision_id)
        || !token(&value.playlist_id)
        || !safe_xml_filename(&value.suggested_filename)
        || !(3..=8).contains(&value.track_count)
        || value.byte_count == 0
        || value.byte_count > MAX_XML_BYTES
        || value.content_utf8.len() != value.byte_count
        || !digest(&value.content_sha256)
        || sha256_hex(value.content_utf8.as_bytes()) != value.content_sha256
        || !digest(&value.m3u8_content_sha256)
        || value.vendor_database_mutation_authorized
        || value.personal_dj_model_training_authorized
        || value.production_activation_authorized
    {
        return Err(VendorInteropError::invalid_response());
    }
    let content = value.content_utf8.as_str();
    if !content.starts_with("<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n")
        || !content.contains("<DJ_PLAYLISTS Version=\"1.0.0\">")
        || !content.contains("<PLAYLISTS>")
        || content.matches("<TRACK TrackID=\"").count() != value.track_count
        || content.matches("<TRACK Key=\"").count() != value.track_count
        || content.matches("Location=\"file://localhost/").count() != value.track_count
        || content.chars().any(|ch| ch == '\0')
    {
        return Err(VendorInteropError::invalid_response());
    }
    Ok(())
}

fn normalize_xml_target(mut target: PathBuf) -> Result<PathBuf, VendorInteropError> {
    let extension = target.extension().and_then(|value| value.to_str());
    match extension {
        None => {
            target.set_extension("xml");
        }
        Some(value) if value.eq_ignore_ascii_case("xml") => {}
        Some(_) => return Err(VendorInteropError::invalid_target()),
    }
    let parent = target.parent().ok_or_else(VendorInteropError::invalid_target)?;
    if !parent.is_dir()
        || target
            .file_name()
            .and_then(|value| value.to_str())
            .is_none()
    {
        return Err(VendorInteropError::invalid_target());
    }
    if target.exists() {
        return Err(VendorInteropError::target_exists());
    }
    Ok(target)
}

fn write_atomic(target: &Path, content: &[u8]) -> Result<(), VendorInteropError> {
    let parent = target.parent().ok_or_else(VendorInteropError::invalid_target)?;
    let temporary = parent.join(format!(
        ".applaylist-vendor-export-{}.tmp",
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
        return Err(VendorInteropError::write_failed());
    }
    Ok(())
}

async fn request_bytes(
    bridge: State<'_, PlaylistVendorInteropBridge>,
    app: &AppHandle,
    path: &'static str,
    revision_id: String,
) -> Result<Vec<u8>, DesktopHostError> {
    if !token(&revision_id) {
        return Err(VendorInteropError::invalid_request().into());
    }
    let resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        bridge.request(path, &revision_id, resource_dir.as_deref())
    })
    .await
    .map_err(|_| {
        DesktopHostError::new(
            "desktop_vendor_interop_task_failed",
            "The vendor interoperability task failed.",
        )
    })?
    .map_err(DesktopHostError::from)
}

#[tauri::command]
pub async fn playlist_vendor_interop_preview(
    revision_id: String,
    bridge: State<'_, PlaylistVendorInteropBridge>,
    app: AppHandle,
) -> Result<VendorInteropPreview, DesktopHostError> {
    let bytes = request_bytes(
        bridge,
        &app,
        "/v1/playlist/vendor/preview",
        revision_id,
    )
    .await?;
    let preview: VendorInteropPreview =
        serde_json::from_slice(&bytes).map_err(|_| VendorInteropError::invalid_response())?;
    validate_preview(&preview).map_err(DesktopHostError::from)?;
    Ok(preview)
}

#[tauri::command]
pub async fn playlist_vendor_interop_export_rekordbox(
    revision_id: String,
    bridge: State<'_, PlaylistVendorInteropBridge>,
    app: AppHandle,
) -> Result<Option<VendorInteropReceipt>, DesktopHostError> {
    let bytes = request_bytes(
        bridge,
        &app,
        "/v1/playlist/vendor/rekordbox/material",
        revision_id,
    )
    .await?;
    let material: RekordboxMaterial =
        serde_json::from_slice(&bytes).map_err(|_| VendorInteropError::invalid_response())?;
    validate_material(&material).map_err(DesktopHostError::from)?;

    let Some(selected) = app
        .dialog()
        .file()
        .set_file_name(&material.suggested_filename)
        .add_filter("rekordbox XML", &["xml"])
        .blocking_save_file()
    else {
        return Ok(None);
    };
    let selected_path = selected
        .into_path()
        .map_err(|_| DesktopHostError::from(VendorInteropError::invalid_target()))?;
    let target = normalize_xml_target(selected_path).map_err(DesktopHostError::from)?;
    write_atomic(&target, material.content_utf8.as_bytes()).map_err(DesktopHostError::from)?;
    let filename = target
        .file_name()
        .and_then(|value| value.to_str())
        .filter(|value| safe_xml_filename(value))
        .ok_or_else(|| DesktopHostError::from(VendorInteropError::invalid_target()))?
        .to_owned();

    Ok(Some(VendorInteropReceipt {
        revision_id: material.revision_id,
        vendor: material.vendor,
        format: material.format,
        filename,
        track_count: material.track_count,
        content_sha256: material.content_sha256,
        bytes_written: material.byte_count,
        m3u8_content_sha256: material.m3u8_content_sha256,
        vendor_database_mutation_authorized: false,
        personal_dj_model_training_authorized: false,
        production_activation_authorized: false,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_preview() -> VendorInteropPreview {
        serde_json::from_value(json!({
            "schema":"applaylist-desktop-vendor-interop-preview-r1",
            "catalog_version":"vendor-interop-catalog-r1",
            "verified_at":"2026-08-19",
            "revision_id":"prv_abc",
            "playlist_id":"plr_abc",
            "revision_index":2,
            "track_count":3,
            "m3u8_path_valid":true,
            "m3u8_content_sha256":"a".repeat(64),
            "capabilities":[
                {"vendor":"rekordbox","status":"documented_format_export","artifact_format":"rekordbox_xml","source_reference_code":"rekordbox_xml_bridge_official","user_action_code":"import_xml_via_bridge","artifact_export_available":true,"vendor_database_mutation_authorized":false},
                {"vendor":"traktor","status":"guidance_only_nml_required","artifact_format":null,"source_reference_code":"traktor_nml_import_official","user_action_code":"use_supported_nml_import_workflow","artifact_export_available":false,"vendor_database_mutation_authorized":false},
                {"vendor":"serato","status":"guidance_only_files_crate","artifact_format":null,"source_reference_code":"serato_files_crate_official","user_action_code":"drag_files_or_folder_to_crate","artifact_export_available":false,"vendor_database_mutation_authorized":false}
            ],
            "personal_dj_model_training_authorized":false,
            "production_activation_authorized":false
        }))
        .expect("valid preview")
    }

    #[test]
    fn preview_rejects_vendor_mutation_or_capability_escalation() {
        let valid = valid_preview();
        assert!(validate_preview(&valid).is_ok());

        let mut escalated = valid_preview();
        escalated.capabilities[1].artifact_export_available = true;
        assert!(validate_preview(&escalated).is_err());

        let mut mutation = valid_preview();
        mutation.capabilities[0].vendor_database_mutation_authorized = true;
        assert!(validate_preview(&mutation).is_err());
    }

    #[test]
    fn material_rejects_digest_or_authority_mismatch() {
        let content = "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n<DJ_PLAYLISTS Version=\"1.0.0\"><COLLECTION Entries=\"3\"><TRACK TrackID=\"1\" Location=\"file://localhost/a\"/><TRACK TrackID=\"2\" Location=\"file://localhost/b\"/><TRACK TrackID=\"3\" Location=\"file://localhost/c\"/></COLLECTION><PLAYLISTS><NODE><TRACK Key=\"1\"/><TRACK Key=\"2\"/><TRACK Key=\"3\"/></NODE></PLAYLISTS></DJ_PLAYLISTS>\n";
        let mut material = RekordboxMaterial {
            schema: "applaylist-desktop-vendor-interop-material-r1".into(),
            vendor: "rekordbox".into(),
            format: "rekordbox_xml".into(),
            revision_id: "prv_abc".into(),
            playlist_id: "plr_abc".into(),
            revision_index: 1,
            suggested_filename: "APPLAYLIST_prv_abc_rekordbox.xml".into(),
            track_count: 3,
            content_utf8: content.into(),
            content_sha256: sha256_hex(content.as_bytes()),
            byte_count: content.len(),
            m3u8_content_sha256: "b".repeat(64),
            vendor_database_mutation_authorized: false,
            personal_dj_model_training_authorized: false,
            production_activation_authorized: false,
        };
        assert!(validate_material(&material).is_ok());
        material.content_sha256 = "c".repeat(64);
        assert!(validate_material(&material).is_err());
    }
}
