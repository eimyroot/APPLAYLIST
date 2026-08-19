use std::{
    collections::HashSet,
    env,
    io::{Read, Write},
    net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Manager, State};
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
const MAX_TOKEN: usize = 256;

#[derive(Debug, Clone)]
pub struct PlaylistEditorBridge {
    executable: Option<PathBuf>,
}

impl PlaylistEditorBridge {
    pub fn from_environment() -> Self {
        Self {
            executable: if cfg!(debug_assertions) {
                env::var_os(SIDECAR_EXECUTABLE_ENV).map(PathBuf::from)
            } else {
                None
            },
        }
    }

    fn executable(&self, resource_dir: Option<&Path>) -> Result<PathBuf, EditorError> {
        if let Some(path) = self.executable.as_ref() {
            let canonical = path.canonicalize().map_err(|_| EditorError::unavailable())?;
            return canonical
                .is_file()
                .then_some(canonical)
                .ok_or_else(EditorError::unavailable);
        }
        let root = resource_dir.ok_or_else(EditorError::not_configured)?;
        let root = root.canonicalize().map_err(|_| EditorError::unavailable())?;
        let binary = root
            .join(BUNDLED_SIDECAR_RESOURCE)
            .canonicalize()
            .map_err(|_| EditorError::unavailable())?;
        if !binary.starts_with(&root) || !binary.is_file() {
            return Err(EditorError::unavailable());
        }
        Ok(binary)
    }

    fn request(
        &self,
        path: &str,
        body: Value,
        resource_dir: Option<&Path>,
    ) -> Result<Value, EditorError> {
        let executable = self.executable(resource_dir)?;
        let mut session = Session::connect(&executable)?;
        let payload = serde_json::to_vec(&body).map_err(|_| EditorError::request_failed())?;
        let response = session.post(path, &payload);
        session.shutdown();
        let (status, bytes) = response?;
        if status != 200 {
            let code = serde_json::from_slice::<Value>(&bytes)
                .ok()
                .and_then(|value| value.get("error").and_then(Value::as_str).map(str::to_owned));
            return Err(EditorError::rejected(code.as_deref()));
        }
        let value = serde_json::from_slice::<Value>(&bytes)
            .map_err(|_| EditorError::invalid_response())?;
        Ok(value)
    }
}

impl Default for PlaylistEditorBridge {
    fn default() -> Self {
        Self::from_environment()
    }
}

#[derive(Debug, Clone)]
struct EditorError {
    code: &'static str,
    message: &'static str,
}

impl EditorError {
    const fn new(code: &'static str, message: &'static str) -> Self {
        Self { code, message }
    }
    const fn not_configured() -> Self {
        Self::new(
            "desktop_playlist_editor_sidecar_not_configured",
            "The playlist editor service is not configured.",
        )
    }
    const fn unavailable() -> Self {
        Self::new(
            "desktop_playlist_editor_sidecar_unavailable",
            "The playlist editor service is unavailable.",
        )
    }
    const fn startup_failed() -> Self {
        Self::new(
            "desktop_playlist_editor_sidecar_startup_failed",
            "The playlist editor service could not start.",
        )
    }
    const fn readiness_failed() -> Self {
        Self::new(
            "desktop_playlist_editor_sidecar_readiness_failed",
            "The playlist editor service did not become ready.",
        )
    }
    const fn request_failed() -> Self {
        Self::new(
            "desktop_playlist_editor_request_failed",
            "The playlist editor request failed.",
        )
    }
    const fn invalid_request() -> Self {
        Self::new(
            "invalid_playlist_editor_request",
            "The playlist editor request is invalid.",
        )
    }
    const fn invalid_response() -> Self {
        Self::new(
            "desktop_playlist_editor_response_invalid",
            "The playlist editor response is invalid.",
        )
    }
    fn rejected(code: Option<&str>) -> Self {
        match code {
            Some("playlist_proposal_stale") => {
                Self::new("playlist_proposal_stale", "The displayed proposal is stale.")
            }
            Some("playlist_revision_stale") => {
                Self::new("playlist_revision_stale", "The playlist revision is stale.")
            }
            Some("playlist_revision_locked_track") => Self::new(
                "playlist_revision_locked_track",
                "A locked track blocks this edit.",
            ),
            Some("playlist_revision_duplicate_track") => Self::new(
                "playlist_revision_duplicate_track",
                "The edit would create a duplicate track.",
            ),
            Some("playlist_revision_membership_changed") => Self::new(
                "playlist_revision_membership_changed",
                "The edit does not match current membership.",
            ),
            Some("playlist_revision_noop") => Self::new(
                "playlist_revision_noop",
                "The edit does not change the current revision.",
            ),
            Some("playlist_revision_not_found") => Self::new(
                "playlist_revision_not_found",
                "The playlist revision was not found.",
            ),
            Some("playlist_replacement_track_unavailable") => Self::new(
                "playlist_replacement_track_unavailable",
                "The replacement track is unavailable.",
            ),
            Some("playlist_replacement_analysis_missing") => Self::new(
                "playlist_replacement_analysis_missing",
                "The replacement track has no analysis evidence.",
            ),
            Some("playlist_replacement_analysis_failed") => Self::new(
                "playlist_replacement_analysis_failed",
                "The replacement track analysis failed.",
            ),
            Some("playlist_replacement_analysis_incomplete") => Self::new(
                "playlist_replacement_analysis_incomplete",
                "The replacement track analysis is incomplete.",
            ),
            Some("invalid_playlist_editor_request") => Self::invalid_request(),
            _ => Self::new(
                "desktop_playlist_editor_rejected",
                "The playlist editor request was rejected.",
            ),
        }
    }
}

impl From<EditorError> for DesktopHostError {
    fn from(value: EditorError) -> Self {
        DesktopHostError::new(value.code, value.message)
    }
}

struct Session {
    child: Child,
    port: u16,
    secret: String,
    nonce: String,
}

impl Session {
    fn connect(executable: &Path) -> Result<Self, EditorError> {
        let secret = random_token();
        let nonce = random_token();
        let mut child = Command::new(executable)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| EditorError::startup_failed())?;
        let envelope = serde_json::to_vec(&json!({
            "protocol": PROTOCOL_VERSION,
            "secret": secret,
            "nonce": nonce
        }))
        .map_err(|_| EditorError::startup_failed())?;
        let mut stdin = child.stdin.take().ok_or_else(EditorError::startup_failed)?;
        stdin
            .write_all(&envelope)
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|_| EditorError::startup_failed())?;
        drop(stdin);
        let line = read_ready(&mut child)?;
        let ready: Value =
            serde_json::from_slice(&line).map_err(|_| EditorError::readiness_failed())?;
        let port = validate_ready(&ready, &nonce)?;
        let (status, health) =
            request_json(port, "GET", "/v1/health", &secret, &nonce, None)?;
        if status != 200 {
            return Err(EditorError::readiness_failed());
        }
        let health: Value =
            serde_json::from_slice(&health).map_err(|_| EditorError::readiness_failed())?;
        let nonce_hash = sha256_hex(&nonce);
        if health.get("status").and_then(Value::as_str) != Some("ready")
            || health.get("protocol").and_then(Value::as_str) != Some(PROTOCOL_VERSION)
            || health.get("nonce_sha256").and_then(Value::as_str) != Some(nonce_hash.as_str())
        {
            return Err(EditorError::readiness_failed());
        }
        Ok(Self {
            child,
            port,
            secret,
            nonce,
        })
    }

    fn post(&mut self, path: &str, body: &[u8]) -> Result<(u16, Vec<u8>), EditorError> {
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

fn read_ready(child: &mut Child) -> Result<Vec<u8>, EditorError> {
    let mut stdout = child.stdout.take().ok_or_else(EditorError::readiness_failed)?;
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
        .map_err(|_| EditorError::readiness_failed())?
        .map_err(|_| EditorError::readiness_failed())
}

fn validate_ready(value: &Value, nonce: &str) -> Result<u16, EditorError> {
    let nonce_hash = sha256_hex(nonce);
    if value.get("event").and_then(Value::as_str) != Some("ready")
        || value.get("protocol").and_then(Value::as_str) != Some(PROTOCOL_VERSION)
        || value.get("host").and_then(Value::as_str) != Some("127.0.0.1")
        || value.get("nonce_sha256").and_then(Value::as_str) != Some(nonce_hash.as_str())
        || value
            .get("process_id")
            .and_then(Value::as_u64)
            .unwrap_or(0)
            == 0
    {
        return Err(EditorError::readiness_failed());
    }
    value
        .get("port")
        .and_then(Value::as_u64)
        .filter(|port| (1..=u16::MAX as u64).contains(port))
        .map(|port| port as u16)
        .ok_or_else(EditorError::readiness_failed)
}

fn request_json(
    port: u16,
    method: &str,
    path: &str,
    secret: &str,
    nonce: &str,
    body: Option<&[u8]>,
) -> Result<(u16, Vec<u8>), EditorError> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream =
        TcpStream::connect_timeout(&address, HTTP_TIMEOUT).map_err(|_| EditorError::request_failed())?;
    stream
        .set_read_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| EditorError::request_failed())?;
    stream
        .set_write_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| EditorError::request_failed())?;
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
        .map_err(|_| EditorError::request_failed())?;
    let mut response = Vec::new();
    stream
        .take(MAX_HTTP_RESPONSE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|_| EditorError::request_failed())?;
    if response.len() as u64 > MAX_HTTP_RESPONSE_BYTES {
        return Err(EditorError::request_failed());
    }
    let boundary = response
        .windows(4)
        .position(|w| w == b"\r\n\r\n")
        .ok_or_else(EditorError::request_failed)?;
    let headers =
        std::str::from_utf8(&response[..boundary]).map_err(|_| EditorError::request_failed())?;
    let mut lines = headers.split("\r\n");
    let mut parts = lines
        .next()
        .ok_or_else(EditorError::request_failed)?
        .split_whitespace();
    if parts.next() != Some("HTTP/1.1") {
        return Err(EditorError::request_failed());
    }
    let status = parts
        .next()
        .and_then(|v| v.parse::<u16>().ok())
        .ok_or_else(EditorError::request_failed)?;
    let mut length = None;
    for line in lines {
        let Some((name, value)) = line.split_once(':') else {
            return Err(EditorError::request_failed());
        };
        if name.eq_ignore_ascii_case("Content-Length") {
            length = value.trim().parse::<usize>().ok();
        }
    }
    let body = &response[boundary + 4..];
    if length != Some(body.len()) {
        return Err(EditorError::request_failed());
    }
    Ok((status, body.to_vec()))
}

fn random_token() -> String {
    format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple())
}

fn sha256_hex(value: &str) -> String {
    format!("{:x}", Sha256::digest(value.as_bytes()))
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

fn exact<'a>(value: &'a Value, keys: &[&str]) -> Option<&'a Map<String, Value>> {
    let object = value.as_object()?;
    if object.len() != keys.len() || keys.iter().any(|key| !object.contains_key(*key)) {
        return None;
    }
    Some(object)
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

fn validate_revision(value: &Value) -> Result<(), EditorError> {
    let object = exact(
        value,
        &[
            "schema",
            "playlist_id",
            "revision_id",
            "parent_revision_id",
            "revision_index",
            "source_proposal_id",
            "source_path_id",
            "operation",
            "content_fingerprint",
            "created_at",
            "sequence",
            "personal_dj_model_training_authorized",
            "production_activation_authorized",
        ],
    )
    .ok_or_else(EditorError::invalid_response)?;
    if object["schema"].as_str() != Some("applaylist-desktop-playlist-revision-r1")
        || !object["playlist_id"].as_str().is_some_and(token)
        || !object["revision_id"].as_str().is_some_and(token)
        || !object["source_proposal_id"].as_str().is_some_and(token)
        || !object["source_path_id"].as_str().is_some_and(token)
        || !matches!(
            object["operation"].as_str(),
            Some("accept" | "reorder" | "lock" | "replace")
        )
        || !object["content_fingerprint"].as_str().is_some_and(|v| {
            v.len() == 64
                && v.bytes()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        })
        || object["personal_dj_model_training_authorized"].as_bool() != Some(false)
        || object["production_activation_authorized"].as_bool() != Some(false)
    {
        return Err(EditorError::invalid_response());
    }
    let index = object["revision_index"]
        .as_u64()
        .ok_or_else(EditorError::invalid_response)?;
    let parent = &object["parent_revision_id"];
    if index == 0 {
        if !parent.is_null() || object["operation"].as_str() != Some("accept") {
            return Err(EditorError::invalid_response());
        }
    } else if !parent.as_str().is_some_and(token) || object["operation"].as_str() == Some("accept") {
        return Err(EditorError::invalid_response());
    }
    let sequence = object["sequence"]
        .as_array()
        .ok_or_else(EditorError::invalid_response)?;
    if !(3..=8).contains(&sequence.len()) {
        return Err(EditorError::invalid_response());
    }
    let mut ids = HashSet::new();
    for (position, item) in sequence.iter().enumerate() {
        let step = exact(item, &["order_index", "track_id", "display_name", "locked"])
            .ok_or_else(EditorError::invalid_response)?;
        if step["order_index"].as_u64() != Some(position as u64)
            || !step["track_id"].as_str().is_some_and(token)
            || !step["display_name"].as_str().is_some_and(display)
            || step["locked"].as_bool().is_none()
            || !ids.insert(step["track_id"].as_str().unwrap())
        {
            return Err(EditorError::invalid_response());
        }
    }
    Ok(())
}

fn validate_history(value: &Value) -> Result<(), EditorError> {
    let object = exact(
        value,
        &[
            "schema",
            "playlist_id",
            "current_revision_id",
            "revisions",
            "history_truncated",
            "personal_dj_model_training_authorized",
            "production_activation_authorized",
        ],
    )
    .ok_or_else(EditorError::invalid_response)?;
    if object["schema"].as_str() != Some("applaylist-desktop-playlist-history-r1")
        || !object["playlist_id"].as_str().is_some_and(token)
        || !object["current_revision_id"].as_str().is_some_and(token)
        || object["history_truncated"].as_bool().is_none()
        || object["personal_dj_model_training_authorized"].as_bool() != Some(false)
        || object["production_activation_authorized"].as_bool() != Some(false)
    {
        return Err(EditorError::invalid_response());
    }
    let revisions = object["revisions"]
        .as_array()
        .ok_or_else(EditorError::invalid_response)?;
    if revisions.is_empty() || revisions.len() > 100 {
        return Err(EditorError::invalid_response());
    }
    let playlist = object["playlist_id"].as_str().unwrap();
    let mut prior = None;
    for revision in revisions {
        validate_revision(revision)?;
        let row = revision.as_object().unwrap();
        if row["playlist_id"].as_str() != Some(playlist) {
            return Err(EditorError::invalid_response());
        }
        let index = row["revision_index"].as_u64().unwrap();
        if prior.is_some_and(|previous| index != previous + 1) {
            return Err(EditorError::invalid_response());
        }
        prior = Some(index);
    }
    if revisions
        .last()
        .and_then(|r| r.get("revision_id"))
        .and_then(Value::as_str)
        != object["current_revision_id"].as_str()
    {
        return Err(EditorError::invalid_response());
    }
    Ok(())
}

fn validate_ids(values: &[String], minimum: usize, maximum: usize) -> Result<(), EditorError> {
    if values.len() < minimum || values.len() > maximum || values.iter().any(|v| !token(v)) {
        return Err(EditorError::invalid_request());
    }
    let set: HashSet<&str> = values.iter().map(String::as_str).collect();
    (set.len() == values.len())
        .then_some(())
        .ok_or_else(EditorError::invalid_request)
}

async fn call(
    bridge: State<'_, PlaylistEditorBridge>,
    app: AppHandle,
    path: &'static str,
    body: Value,
) -> Result<Value, DesktopHostError> {
    let resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        bridge.request(path, body, resource_dir.as_deref())
    })
    .await
    .map_err(|_| {
        DesktopHostError::new(
            "desktop_playlist_editor_task_failed",
            "The playlist editor task failed.",
        )
    })?
    .map_err(DesktopHostError::from)
}

#[tauri::command]
pub async fn playlist_editor_accept(
    track_ids: Vec<String>,
    seed_track_id: String,
    target_track_count: usize,
    proposal_id: String,
    path_id: String,
    bridge: State<'_, PlaylistEditorBridge>,
    app: AppHandle,
) -> Result<Value, DesktopHostError> {
    validate_ids(&track_ids, 3, 24).map_err(DesktopHostError::from)?;
    if !token(&seed_track_id)
        || !track_ids.contains(&seed_track_id)
        || !(3..=8).contains(&target_track_count)
        || target_track_count > track_ids.len()
        || !token(&proposal_id)
        || !token(&path_id)
    {
        return Err(EditorError::invalid_request().into());
    }
    let result = call(
        bridge,
        app,
        "/v1/playlist/editor/accept",
        json!({
            "track_ids":track_ids,
            "seed_track_id":seed_track_id,
            "target_track_count":target_track_count,
            "proposal_id":proposal_id,
            "path_id":path_id,
        }),
    )
    .await?;
    validate_revision(&result).map_err(DesktopHostError::from)?;
    Ok(result)
}

#[tauri::command]
pub async fn playlist_editor_reorder(
    revision_id: String,
    ordered_track_ids: Vec<String>,
    bridge: State<'_, PlaylistEditorBridge>,
    app: AppHandle,
) -> Result<Value, DesktopHostError> {
    if !token(&revision_id) {
        return Err(EditorError::invalid_request().into());
    }
    validate_ids(&ordered_track_ids, 3, 8).map_err(DesktopHostError::from)?;
    let result = call(
        bridge,
        app,
        "/v1/playlist/editor/reorder",
        json!({"revision_id":revision_id,"ordered_track_ids":ordered_track_ids}),
    )
    .await?;
    validate_revision(&result).map_err(DesktopHostError::from)?;
    Ok(result)
}

#[tauri::command]
pub async fn playlist_editor_lock(
    revision_id: String,
    locked_track_ids: Vec<String>,
    bridge: State<'_, PlaylistEditorBridge>,
    app: AppHandle,
) -> Result<Value, DesktopHostError> {
    if !token(&revision_id) {
        return Err(EditorError::invalid_request().into());
    }
    validate_ids(&locked_track_ids, 0, 8).map_err(DesktopHostError::from)?;
    let result = call(
        bridge,
        app,
        "/v1/playlist/editor/lock",
        json!({"revision_id":revision_id,"locked_track_ids":locked_track_ids}),
    )
    .await?;
    validate_revision(&result).map_err(DesktopHostError::from)?;
    Ok(result)
}

#[tauri::command]
pub async fn playlist_editor_replace(
    revision_id: String,
    source_track_id: String,
    replacement_track_id: String,
    bridge: State<'_, PlaylistEditorBridge>,
    app: AppHandle,
) -> Result<Value, DesktopHostError> {
    if !token(&revision_id) || !token(&source_track_id) || !token(&replacement_track_id) {
        return Err(EditorError::invalid_request().into());
    }
    let result = call(
        bridge,
        app,
        "/v1/playlist/editor/replace",
        json!({
            "revision_id":revision_id,
            "source_track_id":source_track_id,
            "replacement_track_id":replacement_track_id,
        }),
    )
    .await?;
    validate_revision(&result).map_err(DesktopHostError::from)?;
    Ok(result)
}

#[tauri::command]
pub async fn playlist_editor_history(
    playlist_id: String,
    bridge: State<'_, PlaylistEditorBridge>,
    app: AppHandle,
) -> Result<Value, DesktopHostError> {
    if !token(&playlist_id) {
        return Err(EditorError::invalid_request().into());
    }
    let result = call(
        bridge,
        app,
        "/v1/playlist/editor/history",
        json!({"playlist_id":playlist_id}),
    )
    .await?;
    validate_history(&result).map_err(DesktopHostError::from)?;
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strict_revision_validation_rejects_authority_and_unknown_fields() {
        let mut revision = json!({
            "schema":"applaylist-desktop-playlist-revision-r1",
            "playlist_id":"plr_abc",
            "revision_id":"prv_abc",
            "parent_revision_id":null,
            "revision_index":0,
            "source_proposal_id":"sor_abc",
            "source_path_id":"sp_abc",
            "operation":"accept",
            "content_fingerprint":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "created_at":"2026-08-19 00:00:00",
            "sequence":[
                {"order_index":0,"track_id":"track:a","display_name":"A","locked":false},
                {"order_index":1,"track_id":"track:b","display_name":"B","locked":false},
                {"order_index":2,"track_id":"track:c","display_name":"C","locked":false}
            ],
            "personal_dj_model_training_authorized":false,
            "production_activation_authorized":false
        });
        assert!(validate_revision(&revision).is_ok());
        revision["production_activation_authorized"] = Value::Bool(true);
        assert!(validate_revision(&revision).is_err());
        revision["production_activation_authorized"] = Value::Bool(false);
        revision
            .as_object_mut()
            .unwrap()
            .insert("path".into(), Value::String("/tmp/a.wav".into()));
        assert!(validate_revision(&revision).is_err());
    }
}
