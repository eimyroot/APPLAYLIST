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
pub struct PlaylistRegenerationBridge {
    executable: Option<PathBuf>,
}

impl PlaylistRegenerationBridge {
    pub fn from_environment() -> Self {
        Self {
            executable: if cfg!(debug_assertions) {
                env::var_os(SIDECAR_EXECUTABLE_ENV).map(PathBuf::from)
            } else {
                None
            },
        }
    }

    fn executable(&self, resource_dir: Option<&Path>) -> Result<PathBuf, RegenerationError> {
        if let Some(path) = self.executable.as_ref() {
            let canonical = path
                .canonicalize()
                .map_err(|_| RegenerationError::unavailable())?;
            return canonical
                .is_file()
                .then_some(canonical)
                .ok_or_else(RegenerationError::unavailable);
        }
        let root = resource_dir.ok_or_else(RegenerationError::not_configured)?;
        let root = root
            .canonicalize()
            .map_err(|_| RegenerationError::unavailable())?;
        let binary = root
            .join(BUNDLED_SIDECAR_RESOURCE)
            .canonicalize()
            .map_err(|_| RegenerationError::unavailable())?;
        if !binary.starts_with(&root) || !binary.is_file() {
            return Err(RegenerationError::unavailable());
        }
        Ok(binary)
    }

    fn request(
        &self,
        path: &str,
        body: Value,
        resource_dir: Option<&Path>,
    ) -> Result<Value, RegenerationError> {
        let executable = self.executable(resource_dir)?;
        let mut session = Session::connect(&executable)?;
        let payload = serde_json::to_vec(&body).map_err(|_| RegenerationError::request_failed())?;
        let response = session.post(path, &payload);
        session.shutdown();
        let (status, bytes) = response?;
        if status != 200 {
            let code = serde_json::from_slice::<Value>(&bytes).ok().and_then(|value| {
                value
                    .get("error")
                    .and_then(Value::as_str)
                    .map(str::to_owned)
            });
            return Err(RegenerationError::rejected(code.as_deref()));
        }
        serde_json::from_slice(&bytes).map_err(|_| RegenerationError::invalid_response())
    }
}

impl Default for PlaylistRegenerationBridge {
    fn default() -> Self {
        Self::from_environment()
    }
}

#[derive(Debug, Clone)]
struct RegenerationError {
    code: &'static str,
    message: &'static str,
}

impl RegenerationError {
    const fn new(code: &'static str, message: &'static str) -> Self {
        Self { code, message }
    }
    const fn not_configured() -> Self {
        Self::new(
            "desktop_playlist_regeneration_sidecar_not_configured",
            "The playlist regeneration service is not configured.",
        )
    }
    const fn unavailable() -> Self {
        Self::new(
            "desktop_playlist_regeneration_sidecar_unavailable",
            "The playlist regeneration service is unavailable.",
        )
    }
    const fn startup_failed() -> Self {
        Self::new(
            "desktop_playlist_regeneration_sidecar_startup_failed",
            "The playlist regeneration service could not start.",
        )
    }
    const fn readiness_failed() -> Self {
        Self::new(
            "desktop_playlist_regeneration_sidecar_readiness_failed",
            "The playlist regeneration service did not become ready.",
        )
    }
    const fn request_failed() -> Self {
        Self::new(
            "desktop_playlist_regeneration_request_failed",
            "The playlist regeneration request failed.",
        )
    }
    const fn invalid_request() -> Self {
        Self::new(
            "invalid_playlist_regeneration_request",
            "The playlist regeneration request is invalid.",
        )
    }
    const fn invalid_response() -> Self {
        Self::new(
            "desktop_playlist_regeneration_response_invalid",
            "The playlist regeneration response is invalid.",
        )
    }
    fn rejected(code: Option<&str>) -> Self {
        match code {
            Some("playlist_revision_stale") => Self::new(
                "playlist_revision_stale",
                "The selected playlist revision is stale.",
            ),
            Some("playlist_revision_not_found") => Self::new(
                "playlist_revision_not_found",
                "The selected playlist revision was not found.",
            ),
            Some("playlist_regeneration_anchor_required") => Self::new(
                "playlist_regeneration_anchor_required",
                "Regeneration R1 requires the first playlist position to be locked.",
            ),
            Some("playlist_regeneration_locked_track_missing") => Self::new(
                "playlist_regeneration_locked_track_missing",
                "The regeneration scope must contain every locked track.",
            ),
            Some("playlist_regeneration_evidence_unavailable") => Self::new(
                "playlist_regeneration_evidence_unavailable",
                "Required regeneration evidence is unavailable.",
            ),
            Some("playlist_regeneration_projection_failed") => Self::new(
                "playlist_regeneration_projection_failed",
                "No safe regeneration projection is available.",
            ),
            Some("playlist_regeneration_stale") => Self::new(
                "playlist_regeneration_stale",
                "The displayed regeneration preview is stale.",
            ),
            Some("playlist_revision_noop") => Self::new(
                "playlist_revision_noop",
                "The regeneration does not change the current revision.",
            ),
            Some("invalid_playlist_editor_request" | "invalid_playlist_regeneration_request") => {
                Self::invalid_request()
            }
            _ => Self::new(
                "desktop_playlist_regeneration_rejected",
                "The playlist regeneration request was rejected.",
            ),
        }
    }
}

impl From<RegenerationError> for DesktopHostError {
    fn from(value: RegenerationError) -> Self {
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
    fn connect(executable: &Path) -> Result<Self, RegenerationError> {
        let secret = random_token();
        let nonce = random_token();
        let mut child = Command::new(executable)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| RegenerationError::startup_failed())?;
        let envelope = serde_json::to_vec(&json!({
            "protocol": PROTOCOL_VERSION,
            "secret": secret,
            "nonce": nonce,
        }))
        .map_err(|_| RegenerationError::startup_failed())?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(RegenerationError::startup_failed)?;
        stdin
            .write_all(&envelope)
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|_| RegenerationError::startup_failed())?;
        drop(stdin);

        let line = read_ready(&mut child)?;
        let ready: Value =
            serde_json::from_slice(&line).map_err(|_| RegenerationError::readiness_failed())?;
        let port = validate_ready(&ready, &nonce)?;
        let (status, health) = request_json(port, "GET", "/v1/health", &secret, &nonce, None)?;
        if status != 200 {
            return Err(RegenerationError::readiness_failed());
        }
        let health: Value =
            serde_json::from_slice(&health).map_err(|_| RegenerationError::readiness_failed())?;
        let nonce_hash = sha256_hex(nonce.as_bytes());
        if health.get("status").and_then(Value::as_str) != Some("ready")
            || health.get("protocol").and_then(Value::as_str) != Some(PROTOCOL_VERSION)
            || health.get("nonce_sha256").and_then(Value::as_str) != Some(nonce_hash.as_str())
        {
            return Err(RegenerationError::readiness_failed());
        }
        Ok(Self {
            child,
            port,
            secret,
            nonce,
        })
    }

    fn post(&mut self, path: &str, body: &[u8]) -> Result<(u16, Vec<u8>), RegenerationError> {
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

fn read_ready(child: &mut Child) -> Result<Vec<u8>, RegenerationError> {
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(RegenerationError::readiness_failed)?;
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
        .map_err(|_| RegenerationError::readiness_failed())?
        .map_err(|_| RegenerationError::readiness_failed())
}

fn validate_ready(value: &Value, nonce: &str) -> Result<u16, RegenerationError> {
    let nonce_hash = sha256_hex(nonce.as_bytes());
    if value.get("event").and_then(Value::as_str) != Some("ready")
        || value.get("protocol").and_then(Value::as_str) != Some(PROTOCOL_VERSION)
        || value.get("host").and_then(Value::as_str) != Some("127.0.0.1")
        || value.get("nonce_sha256").and_then(Value::as_str) != Some(nonce_hash.as_str())
        || value.get("process_id").and_then(Value::as_u64).unwrap_or(0) == 0
    {
        return Err(RegenerationError::readiness_failed());
    }
    value
        .get("port")
        .and_then(Value::as_u64)
        .filter(|port| (1..=u16::MAX as u64).contains(port))
        .map(|port| port as u16)
        .ok_or_else(RegenerationError::readiness_failed)
}

fn request_json(
    port: u16,
    method: &str,
    path: &str,
    secret: &str,
    nonce: &str,
    body: Option<&[u8]>,
) -> Result<(u16, Vec<u8>), RegenerationError> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, HTTP_TIMEOUT)
        .map_err(|_| RegenerationError::request_failed())?;
    stream
        .set_read_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| RegenerationError::request_failed())?;
    stream
        .set_write_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| RegenerationError::request_failed())?;
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
        .map_err(|_| RegenerationError::request_failed())?;
    let mut response = Vec::new();
    std::io::Read::by_ref(&mut stream)
        .take(MAX_HTTP_RESPONSE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|_| RegenerationError::request_failed())?;
    if response.len() as u64 > MAX_HTTP_RESPONSE_BYTES {
        return Err(RegenerationError::request_failed());
    }
    let boundary = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(RegenerationError::request_failed)?;
    let headers = std::str::from_utf8(&response[..boundary])
        .map_err(|_| RegenerationError::request_failed())?;
    let mut lines = headers.split("\r\n");
    let mut parts = lines
        .next()
        .ok_or_else(RegenerationError::request_failed)?
        .split_whitespace();
    if parts.next() != Some("HTTP/1.1") {
        return Err(RegenerationError::request_failed());
    }
    let status = parts
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(RegenerationError::request_failed)?;
    let mut length = None;
    for line in lines {
        let Some((name, value)) = line.split_once(':') else {
            return Err(RegenerationError::request_failed());
        };
        if name.eq_ignore_ascii_case("Content-Length") {
            length = value.trim().parse::<usize>().ok();
        }
    }
    let body = &response[boundary + 4..];
    if length != Some(body.len()) {
        return Err(RegenerationError::request_failed());
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

fn digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn exact<'a>(value: &'a Value, keys: &[&str]) -> Option<&'a Map<String, Value>> {
    let object = value.as_object()?;
    if object.len() != keys.len() || keys.iter().any(|key| !object.contains_key(*key)) {
        return None;
    }
    Some(object)
}

fn token_array(value: &Value, maximum: usize) -> bool {
    value.as_array().is_some_and(|items| {
        items.len() <= maximum && items.iter().all(|item| item.as_str().is_some_and(token))
    })
}

fn validate_regeneration(value: &Value, revision_id: &str) -> Result<(), RegenerationError> {
    let object = exact(
        value,
        &[
            "schema",
            "playlist_id",
            "parent_revision_id",
            "regeneration_id",
            "candidate_pool_count",
            "candidate_pool_sha256",
            "locked_positions",
            "alternatives",
            "reason_codes",
            "warning_codes",
            "budget_exhausted",
            "missing_evidence_detected",
            "deterministic_ordering",
            "playlist_mutation_authorized",
            "personal_dj_model_training_authorized",
            "production_activation_authorized",
        ],
    )
    .ok_or_else(RegenerationError::invalid_response)?;
    if object["schema"].as_str() != Some("applaylist-desktop-playlist-regeneration-r1")
        || !object["playlist_id"].as_str().is_some_and(token)
        || object["parent_revision_id"].as_str() != Some(revision_id)
        || !object["regeneration_id"].as_str().is_some_and(token)
        || !(3..=24).contains(&object["candidate_pool_count"].as_u64().unwrap_or(0))
        || !object["candidate_pool_sha256"].as_str().is_some_and(digest)
        || object["budget_exhausted"].as_bool().is_none()
        || object["missing_evidence_detected"].as_bool().is_none()
        || object["deterministic_ordering"].as_bool() != Some(true)
        || object["playlist_mutation_authorized"].as_bool() != Some(false)
        || object["personal_dj_model_training_authorized"].as_bool() != Some(false)
        || object["production_activation_authorized"].as_bool() != Some(false)
        || !token_array(&object["reason_codes"], 128)
        || !token_array(&object["warning_codes"], 128)
    {
        return Err(RegenerationError::invalid_response());
    }

    let locks = object["locked_positions"]
        .as_array()
        .ok_or_else(RegenerationError::invalid_response)?;
    if locks.is_empty() || locks.len() > 8 {
        return Err(RegenerationError::invalid_response());
    }
    let mut lock_positions = HashSet::new();
    for lock in locks {
        let row = exact(lock, &["order_index", "track_id"])
            .ok_or_else(RegenerationError::invalid_response)?;
        let index = row["order_index"]
            .as_u64()
            .ok_or_else(RegenerationError::invalid_response)?;
        if index > 7
            || !row["track_id"].as_str().is_some_and(token)
            || !lock_positions.insert(index)
        {
            return Err(RegenerationError::invalid_response());
        }
    }
    if !lock_positions.contains(&0) {
        return Err(RegenerationError::invalid_response());
    }

    let alternatives = object["alternatives"]
        .as_array()
        .ok_or_else(RegenerationError::invalid_response)?;
    if alternatives.len() > 3 {
        return Err(RegenerationError::invalid_response());
    }
    for (alternative_index, alternative) in alternatives.iter().enumerate() {
        let row = exact(
            alternative,
            &["path_id", "rank", "sequence", "objective", "explanation_codes"],
        )
        .ok_or_else(RegenerationError::invalid_response)?;
        if !row["path_id"].as_str().is_some_and(token)
            || row["rank"].as_u64() != Some((alternative_index + 1) as u64)
            || !token_array(&row["explanation_codes"], 128)
        {
            return Err(RegenerationError::invalid_response());
        }
        let objective = exact(
            &row["objective"],
            &[
                "depth",
                "mean_candidate_score",
                "minimum_candidate_score",
                "required_track_completion",
                "remaining_required_count",
                "target_reached",
            ],
        )
        .ok_or_else(RegenerationError::invalid_response)?;
        if objective["depth"].as_u64().is_none()
            || objective["mean_candidate_score"].as_f64().is_none()
            || objective["minimum_candidate_score"].as_f64().is_none()
            || objective["required_track_completion"].as_f64().is_none()
            || objective["remaining_required_count"].as_u64().is_none()
            || objective["target_reached"].as_bool().is_none()
        {
            return Err(RegenerationError::invalid_response());
        }
        let sequence = row["sequence"]
            .as_array()
            .ok_or_else(RegenerationError::invalid_response)?;
        if !(3..=8).contains(&sequence.len()) {
            return Err(RegenerationError::invalid_response());
        }
        let mut ids = HashSet::new();
        for (index, step) in sequence.iter().enumerate() {
            let item = exact(step, &["order_index", "track_id", "display_name", "locked"])
                .ok_or_else(RegenerationError::invalid_response)?;
            if item["order_index"].as_u64() != Some(index as u64)
                || !item["track_id"].as_str().is_some_and(token)
                || !item["display_name"].as_str().is_some_and(display)
                || item["locked"].as_bool().is_none()
                || !ids.insert(item["track_id"].as_str().unwrap())
            {
                return Err(RegenerationError::invalid_response());
            }
            let expected_lock = locks.iter().find(|lock| {
                lock.get("order_index").and_then(Value::as_u64) == Some(index as u64)
            });
            match expected_lock {
                Some(lock) => {
                    if item["locked"].as_bool() != Some(true)
                        || item["track_id"].as_str()
                            != lock.get("track_id").and_then(Value::as_str)
                    {
                        return Err(RegenerationError::invalid_response());
                    }
                }
                None if item["locked"].as_bool() != Some(false) => {
                    return Err(RegenerationError::invalid_response());
                }
                None => {}
            }
        }
    }
    Ok(())
}

fn validate_revision(value: &Value, parent_revision_id: &str) -> Result<(), RegenerationError> {
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
    .ok_or_else(RegenerationError::invalid_response)?;
    if object["schema"].as_str() != Some("applaylist-desktop-playlist-revision-r1")
        || !object["playlist_id"].as_str().is_some_and(token)
        || !object["revision_id"].as_str().is_some_and(token)
        || object["parent_revision_id"].as_str() != Some(parent_revision_id)
        || object["revision_index"].as_u64().unwrap_or(0) == 0
        || !object["source_proposal_id"].as_str().is_some_and(token)
        || !object["source_path_id"].as_str().is_some_and(token)
        || object["operation"].as_str() != Some("regenerate")
        || !object["content_fingerprint"].as_str().is_some_and(digest)
        || object["personal_dj_model_training_authorized"].as_bool() != Some(false)
        || object["production_activation_authorized"].as_bool() != Some(false)
    {
        return Err(RegenerationError::invalid_response());
    }
    let sequence = object["sequence"]
        .as_array()
        .ok_or_else(RegenerationError::invalid_response)?;
    if !(3..=8).contains(&sequence.len()) {
        return Err(RegenerationError::invalid_response());
    }
    let mut ids = HashSet::new();
    for (index, step) in sequence.iter().enumerate() {
        let item = exact(step, &["order_index", "track_id", "display_name", "locked"])
            .ok_or_else(RegenerationError::invalid_response)?;
        if item["order_index"].as_u64() != Some(index as u64)
            || !item["track_id"].as_str().is_some_and(token)
            || !item["display_name"].as_str().is_some_and(display)
            || item["locked"].as_bool().is_none()
            || !ids.insert(item["track_id"].as_str().unwrap())
        {
            return Err(RegenerationError::invalid_response());
        }
    }
    Ok(())
}

fn validate_ids(values: &[String]) -> Result<(), RegenerationError> {
    if !(3..=24).contains(&values.len()) || values.iter().any(|value| !token(value)) {
        return Err(RegenerationError::invalid_request());
    }
    let unique: HashSet<&str> = values.iter().map(String::as_str).collect();
    (unique.len() == values.len())
        .then_some(())
        .ok_or_else(RegenerationError::invalid_request)
}

async fn call(
    bridge: State<'_, PlaylistRegenerationBridge>,
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
            "desktop_playlist_regeneration_task_failed",
            "The playlist regeneration task failed.",
        )
    })?
    .map_err(DesktopHostError::from)
}

#[tauri::command]
pub async fn playlist_editor_regeneration_preview(
    revision_id: String,
    candidate_track_ids: Vec<String>,
    bridge: State<'_, PlaylistRegenerationBridge>,
    app: AppHandle,
) -> Result<Value, DesktopHostError> {
    if !token(&revision_id) {
        return Err(RegenerationError::invalid_request().into());
    }
    validate_ids(&candidate_track_ids).map_err(DesktopHostError::from)?;
    let result = call(
        bridge,
        app,
        "/v1/playlist/editor/regeneration/preview",
        json!({"revision_id":revision_id,"candidate_track_ids":candidate_track_ids}),
    )
    .await?;
    validate_regeneration(&result, &revision_id).map_err(DesktopHostError::from)?;
    Ok(result)
}

#[tauri::command]
pub async fn playlist_editor_regeneration_apply(
    revision_id: String,
    candidate_track_ids: Vec<String>,
    regeneration_id: String,
    path_id: String,
    bridge: State<'_, PlaylistRegenerationBridge>,
    app: AppHandle,
) -> Result<Value, DesktopHostError> {
    if !token(&revision_id) || !token(&regeneration_id) || !token(&path_id) {
        return Err(RegenerationError::invalid_request().into());
    }
    validate_ids(&candidate_track_ids).map_err(DesktopHostError::from)?;
    let expected_parent = revision_id.clone();
    let result = call(
        bridge,
        app,
        "/v1/playlist/editor/regeneration/apply",
        json!({
            "revision_id":revision_id,
            "candidate_track_ids":candidate_track_ids,
            "regeneration_id":regeneration_id,
            "path_id":path_id,
        }),
    )
    .await?;
    validate_revision(&result, &expected_parent).map_err(DesktopHostError::from)?;
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preview_validation_rejects_authority_escalation() {
        let mut value = json!({
            "schema":"applaylist-desktop-playlist-regeneration-r1",
            "playlist_id":"plr_abc",
            "parent_revision_id":"prv_parent",
            "regeneration_id":"spr_abc",
            "candidate_pool_count":3,
            "candidate_pool_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "locked_positions":[{"order_index":0,"track_id":"track:a"}],
            "alternatives":[],
            "reason_codes":[],
            "warning_codes":[],
            "budget_exhausted":false,
            "missing_evidence_detected":false,
            "deterministic_ordering":true,
            "playlist_mutation_authorized":false,
            "personal_dj_model_training_authorized":false,
            "production_activation_authorized":false
        });
        assert!(validate_regeneration(&value, "prv_parent").is_ok());
        value["playlist_mutation_authorized"] = Value::Bool(true);
        assert!(validate_regeneration(&value, "prv_parent").is_err());
    }
}
