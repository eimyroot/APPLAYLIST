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
pub struct TransitionInspectorBridge {
    executable: Option<PathBuf>,
}

impl TransitionInspectorBridge {
    pub fn from_environment() -> Self {
        Self {
            executable: if cfg!(debug_assertions) {
                env::var_os(SIDECAR_EXECUTABLE_ENV).map(PathBuf::from)
            } else {
                None
            },
        }
    }

    fn executable(&self, resource_dir: Option<&Path>) -> Result<PathBuf, InspectorError> {
        if let Some(path) = self.executable.as_ref() {
            let canonical = path
                .canonicalize()
                .map_err(|_| InspectorError::unavailable())?;
            return canonical
                .is_file()
                .then_some(canonical)
                .ok_or_else(InspectorError::unavailable);
        }
        let root = resource_dir.ok_or_else(InspectorError::not_configured)?;
        let root = root
            .canonicalize()
            .map_err(|_| InspectorError::unavailable())?;
        let binary = root
            .join(BUNDLED_SIDECAR_RESOURCE)
            .canonicalize()
            .map_err(|_| InspectorError::unavailable())?;
        if !binary.starts_with(&root) || !binary.is_file() {
            return Err(InspectorError::unavailable());
        }
        Ok(binary)
    }

    fn request(
        &self,
        revision_id: &str,
        pair_index: usize,
        resource_dir: Option<&Path>,
    ) -> Result<Value, InspectorError> {
        let executable = self.executable(resource_dir)?;
        let mut session = Session::connect(&executable)?;
        let payload = serde_json::to_vec(&json!({
            "revision_id": revision_id,
            "pair_index": pair_index,
        }))
        .map_err(|_| InspectorError::request_failed())?;
        let response = session.post("/v1/playlist/transition/inspect", &payload);
        session.shutdown();
        let (status, bytes) = response?;
        if status != 200 {
            let code = serde_json::from_slice::<Value>(&bytes)
                .ok()
                .and_then(|value| {
                    value
                        .get("error")
                        .and_then(Value::as_str)
                        .map(str::to_owned)
                });
            return Err(InspectorError::rejected(code.as_deref()));
        }
        serde_json::from_slice(&bytes).map_err(|_| InspectorError::invalid_response())
    }
}

impl Default for TransitionInspectorBridge {
    fn default() -> Self {
        Self::from_environment()
    }
}

#[derive(Debug, Clone)]
struct InspectorError {
    code: &'static str,
    message: &'static str,
}

impl InspectorError {
    const fn new(code: &'static str, message: &'static str) -> Self {
        Self { code, message }
    }
    const fn not_configured() -> Self {
        Self::new(
            "desktop_transition_inspector_sidecar_not_configured",
            "The transition inspector service is not configured.",
        )
    }
    const fn unavailable() -> Self {
        Self::new(
            "desktop_transition_inspector_sidecar_unavailable",
            "The transition inspector service is unavailable.",
        )
    }
    const fn startup_failed() -> Self {
        Self::new(
            "desktop_transition_inspector_sidecar_startup_failed",
            "The transition inspector service could not start.",
        )
    }
    const fn readiness_failed() -> Self {
        Self::new(
            "desktop_transition_inspector_sidecar_readiness_failed",
            "The transition inspector service did not become ready.",
        )
    }
    const fn request_failed() -> Self {
        Self::new(
            "desktop_transition_inspector_request_failed",
            "The transition inspection request failed.",
        )
    }
    const fn invalid_request() -> Self {
        Self::new(
            "invalid_transition_inspection_request",
            "The transition inspection request is invalid.",
        )
    }
    const fn invalid_response() -> Self {
        Self::new(
            "desktop_transition_inspector_response_invalid",
            "The transition inspection response is invalid.",
        )
    }
    fn rejected(code: Option<&str>) -> Self {
        match code {
            Some("transition_inspection_revision_not_found") => Self::new(
                "transition_inspection_revision_not_found",
                "The selected playlist revision was not found.",
            ),
            Some("transition_inspection_snapshot_missing") => Self::new(
                "transition_inspection_snapshot_missing",
                "The selected transition snapshot is unavailable.",
            ),
            Some("transition_inspection_identity_mismatch") => Self::new(
                "transition_inspection_identity_mismatch",
                "Persisted transition evidence does not match the selected revision pair.",
            ),
            Some("invalid_transition_inspection_request") => Self::invalid_request(),
            _ => Self::new(
                "desktop_transition_inspector_rejected",
                "The transition inspection request was rejected.",
            ),
        }
    }
}

impl From<InspectorError> for DesktopHostError {
    fn from(value: InspectorError) -> Self {
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
    fn connect(executable: &Path) -> Result<Self, InspectorError> {
        let secret = random_token();
        let nonce = random_token();
        let mut child = Command::new(executable)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| InspectorError::startup_failed())?;
        let envelope = serde_json::to_vec(&json!({
            "protocol": PROTOCOL_VERSION,
            "secret": secret,
            "nonce": nonce,
        }))
        .map_err(|_| InspectorError::startup_failed())?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(InspectorError::startup_failed)?;
        stdin
            .write_all(&envelope)
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|_| InspectorError::startup_failed())?;
        drop(stdin);

        let line = read_ready(&mut child)?;
        let ready: Value =
            serde_json::from_slice(&line).map_err(|_| InspectorError::readiness_failed())?;
        let port = validate_ready(&ready, &nonce)?;
        let (status, health) = request_json(port, "GET", "/v1/health", &secret, &nonce, None)?;
        if status != 200 {
            return Err(InspectorError::readiness_failed());
        }
        let health: Value =
            serde_json::from_slice(&health).map_err(|_| InspectorError::readiness_failed())?;
        let nonce_hash = sha256_hex(nonce.as_bytes());
        if health.get("status").and_then(Value::as_str) != Some("ready")
            || health.get("protocol").and_then(Value::as_str) != Some(PROTOCOL_VERSION)
            || health.get("nonce_sha256").and_then(Value::as_str) != Some(nonce_hash.as_str())
        {
            return Err(InspectorError::readiness_failed());
        }
        Ok(Self {
            child,
            port,
            secret,
            nonce,
        })
    }

    fn post(&mut self, path: &str, body: &[u8]) -> Result<(u16, Vec<u8>), InspectorError> {
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

fn read_ready(child: &mut Child) -> Result<Vec<u8>, InspectorError> {
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(InspectorError::readiness_failed)?;
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
        .map_err(|_| InspectorError::readiness_failed())?
        .map_err(|_| InspectorError::readiness_failed())
}

fn validate_ready(value: &Value, nonce: &str) -> Result<u16, InspectorError> {
    let nonce_hash = sha256_hex(nonce.as_bytes());
    if value.get("event").and_then(Value::as_str) != Some("ready")
        || value.get("protocol").and_then(Value::as_str) != Some(PROTOCOL_VERSION)
        || value.get("host").and_then(Value::as_str) != Some("127.0.0.1")
        || value.get("nonce_sha256").and_then(Value::as_str) != Some(nonce_hash.as_str())
        || value.get("process_id").and_then(Value::as_u64).unwrap_or(0) == 0
    {
        return Err(InspectorError::readiness_failed());
    }
    value
        .get("port")
        .and_then(Value::as_u64)
        .filter(|port| (1..=u16::MAX as u64).contains(port))
        .map(|port| port as u16)
        .ok_or_else(InspectorError::readiness_failed)
}

fn request_json(
    port: u16,
    method: &str,
    path: &str,
    secret: &str,
    nonce: &str,
    body: Option<&[u8]>,
) -> Result<(u16, Vec<u8>), InspectorError> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, HTTP_TIMEOUT)
        .map_err(|_| InspectorError::request_failed())?;
    stream
        .set_read_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| InspectorError::request_failed())?;
    stream
        .set_write_timeout(Some(HTTP_TIMEOUT))
        .map_err(|_| InspectorError::request_failed())?;
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
        .map_err(|_| InspectorError::request_failed())?;
    let mut response = Vec::new();
    std::io::Read::by_ref(&mut stream)
        .take(MAX_HTTP_RESPONSE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|_| InspectorError::request_failed())?;
    if response.len() as u64 > MAX_HTTP_RESPONSE_BYTES {
        return Err(InspectorError::request_failed());
    }
    let boundary = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(InspectorError::request_failed)?;
    let headers = std::str::from_utf8(&response[..boundary])
        .map_err(|_| InspectorError::request_failed())?;
    let mut lines = headers.split("\r\n");
    let mut parts = lines
        .next()
        .ok_or_else(InspectorError::request_failed)?
        .split_whitespace();
    if parts.next() != Some("HTTP/1.1") {
        return Err(InspectorError::request_failed());
    }
    let status = parts
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(InspectorError::request_failed)?;
    let mut length = None;
    for line in lines {
        let Some((name, value)) = line.split_once(':') else {
            return Err(InspectorError::request_failed());
        };
        if name.eq_ignore_ascii_case("Content-Length") {
            length = value.trim().parse::<usize>().ok();
        }
    }
    let body = &response[boundary + 4..];
    if length != Some(body.len()) {
        return Err(InspectorError::request_failed());
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

fn safe_label(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 512
        && value.trim() == value
        && !value.starts_with('/')
        && !value.starts_with("\\\\")
        && !(value.len() >= 3
            && value.as_bytes()[0].is_ascii_alphabetic()
            && value.as_bytes()[1] == b':'
            && matches!(value.as_bytes()[2], b'/' | b'\\'))
        && !value.chars().any(char::is_control)
}

fn digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn exact_keys(object: &Map<String, Value>, expected: &[&str]) -> bool {
    if object.len() != expected.len() {
        return false;
    }
    let expected: HashSet<&str> = expected.iter().copied().collect();
    object.keys().all(|key| expected.contains(key.as_str()))
}

fn valid_item(value: &Value, expected_index: usize) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    exact_keys(object, &["order_index", "track_id", "display_name", "locked"])
        && object.get("order_index").and_then(Value::as_u64) == Some(expected_index as u64)
        && object.get("track_id").and_then(Value::as_str).is_some_and(token)
        && object
            .get("display_name")
            .and_then(Value::as_str)
            .is_some_and(safe_label)
        && object.get("locked").and_then(Value::as_bool).is_some()
}

fn valid_snapshot(value: &Value) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    if !exact_keys(
        object,
        &[
            "snapshot_id",
            "transition_id",
            "source_segment_id",
            "target_segment_id",
            "assessment_version",
            "policy_version",
            "context_id",
            "context_version",
            "payload_sha256",
            "created_at",
        ],
    ) {
        return false;
    }
    for key in [
        "snapshot_id",
        "transition_id",
        "source_segment_id",
        "target_segment_id",
        "assessment_version",
        "policy_version",
        "context_id",
        "context_version",
    ] {
        if !object.get(key).and_then(Value::as_str).is_some_and(token) {
            return false;
        }
    }
    object
        .get("payload_sha256")
        .and_then(Value::as_str)
        .is_some_and(digest)
        && object
            .get("created_at")
            .and_then(Value::as_str)
            .is_some_and(|value| !value.is_empty() && value.len() <= 64 && !value.chars().any(char::is_control))
}

fn valid_confidence(value: &Value) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    exact_keys(
        object,
        &["score", "calibration_state", "evidence_count", "disagreement"],
    ) && object
        .get("calibration_state")
        .and_then(Value::as_str)
        .is_some_and(|value| matches!(value, "unknown" | "uncalibrated" | "calibrated"))
        && object.get("evidence_count").and_then(Value::as_u64).unwrap_or(0) >= 1
}

fn valid_token_array(value: &Value, max: usize) -> bool {
    value.as_array().is_some_and(|items| {
        items.len() <= max
            && items
                .iter()
                .all(|item| item.as_str().is_some_and(token))
    })
}

fn valid_assessment(value: &Value) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    if !exact_keys(
        object,
        &[
            "transition_id",
            "source_segment_id",
            "target_segment_id",
            "assessment_version",
            "policy_version",
            "music_dna_revision_refs",
            "created_at",
            "compatibility",
            "risk",
            "cost",
            "energy_effect",
            "candidate_strategies",
            "preferred_strategy",
            "usable_window",
            "contextual_projection",
            "confidence",
            "explanations",
            "evidence_refs",
            "warnings",
        ],
    ) {
        return false;
    }
    for key in [
        "transition_id",
        "source_segment_id",
        "target_segment_id",
        "assessment_version",
        "policy_version",
    ] {
        if !object.get(key).and_then(Value::as_str).is_some_and(token) {
            return false;
        }
    }
    if !object
        .get("music_dna_revision_refs")
        .and_then(Value::as_array)
        .is_some_and(|items| items.len() == 2 && items.iter().all(|item| item.as_str().is_some_and(token)))
        || !object
            .get("created_at")
            .and_then(Value::as_str)
            .is_some_and(|value| !value.is_empty() && value.len() <= 64)
        || !valid_confidence(&object["confidence"])
        || !valid_token_array(&object["evidence_refs"], 64)
        || !object.get("warnings").and_then(Value::as_array).is_some_and(|items| {
            items.len() <= 64
                && items.iter().all(|item| {
                    item.as_str().is_some_and(|value| {
                        value.len() <= 512 && !value.starts_with('/') && !value.chars().any(char::is_control)
                    })
                })
        })
    {
        return false;
    }

    let Some(strategies) = object.get("candidate_strategies").and_then(Value::as_array) else {
        return false;
    };
    if strategies.is_empty() || strategies.len() > 16 {
        return false;
    }
    for strategy in strategies {
        let Some(item) = strategy.as_object() else {
            return false;
        };
        if !exact_keys(
            item,
            &[
                "strategy",
                "suitability",
                "required_capabilities",
                "explanation_codes",
            ],
        ) || !item.get("strategy").and_then(Value::as_str).is_some_and(token)
            || !valid_token_array(&item["required_capabilities"], 32)
            || !valid_token_array(&item["explanation_codes"], 32)
        {
            return false;
        }
    }

    let Some(window) = object.get("usable_window").and_then(Value::as_object) else {
        return false;
    };
    if !exact_keys(
        window,
        &[
            "source_start_seconds",
            "source_end_seconds",
            "target_start_seconds",
            "target_end_seconds",
            "source_bar_count",
            "target_bar_count",
            "confidence",
        ],
    ) || !valid_confidence(&window["confidence"])
    {
        return false;
    }

    let Some(projection) = object
        .get("contextual_projection")
        .and_then(Value::as_object)
    else {
        return false;
    };
    if !exact_keys(
        projection,
        &[
            "context_id",
            "context_version",
            "score",
            "blocked_reasons",
            "rank_features",
            "confidence",
            "explanation_codes",
        ],
    ) || !projection
        .get("context_id")
        .and_then(Value::as_str)
        .is_some_and(token)
        || !projection
            .get("context_version")
            .and_then(Value::as_str)
            .is_some_and(token)
        || !valid_token_array(&projection["blocked_reasons"], 32)
        || !valid_token_array(&projection["rank_features"], 32)
        || !valid_token_array(&projection["explanation_codes"], 32)
        || !valid_confidence(&projection["confidence"])
    {
        return false;
    }

    object.get("explanations").and_then(Value::as_array).is_some_and(|items| {
        items.len() <= 64
            && items.iter().all(|value| {
                let Some(item) = value.as_object() else {
                    return false;
                };
                exact_keys(item, &["code", "severity", "dimension", "evidence_refs", "confidence"])
                    && item.get("code").and_then(Value::as_str).is_some_and(token)
                    && item.get("severity").and_then(Value::as_str).is_some_and(token)
                    && item.get("dimension").and_then(Value::as_str).is_some_and(token)
                    && valid_token_array(&item["evidence_refs"], 64)
                    && valid_confidence(&item["confidence"])
            })
    })
}

fn validate_response(value: &Value, revision_id: &str, pair_index: usize) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    if !exact_keys(
        object,
        &[
            "schema",
            "revision_id",
            "playlist_id",
            "revision_index",
            "pair_index",
            "source",
            "target",
            "available_snapshots",
            "personal_dj_model_training_authorized",
            "production_activation_authorized",
            "transition_recomputation_authorized",
            "playlist_mutation_authorized",
            "state",
            "selected_snapshot_id",
            "assessment",
        ],
    ) || object.get("schema").and_then(Value::as_str)
        != Some("applaylist-desktop-transition-inspection-r1")
        || object.get("revision_id").and_then(Value::as_str) != Some(revision_id)
        || !object.get("playlist_id").and_then(Value::as_str).is_some_and(token)
        || object.get("pair_index").and_then(Value::as_u64) != Some(pair_index as u64)
        || !valid_item(&object["source"], pair_index)
        || !valid_item(&object["target"], pair_index + 1)
        || object
            .get("personal_dj_model_training_authorized")
            .and_then(Value::as_bool)
            != Some(false)
        || object
            .get("production_activation_authorized")
            .and_then(Value::as_bool)
            != Some(false)
        || object
            .get("transition_recomputation_authorized")
            .and_then(Value::as_bool)
            != Some(false)
        || object
            .get("playlist_mutation_authorized")
            .and_then(Value::as_bool)
            != Some(false)
    {
        return false;
    }

    let Some(snapshots) = object.get("available_snapshots").and_then(Value::as_array) else {
        return false;
    };
    if snapshots.len() > 16 || !snapshots.iter().all(valid_snapshot) {
        return false;
    }
    match object.get("state").and_then(Value::as_str) {
        Some("missing") => {
            snapshots.is_empty()
                && object.get("selected_snapshot_id") == Some(&Value::Null)
                && object.get("assessment") == Some(&Value::Null)
        }
        Some("present") => {
            let selected = object.get("selected_snapshot_id").and_then(Value::as_str);
            !snapshots.is_empty()
                && selected.is_some_and(token)
                && snapshots[0].get("snapshot_id").and_then(Value::as_str) == selected
                && object.get("assessment").is_some_and(valid_assessment)
        }
        _ => false,
    }
}

#[tauri::command]
pub async fn playlist_transition_inspect(
    revision_id: String,
    pair_index: usize,
    bridge: State<'_, TransitionInspectorBridge>,
    app: AppHandle,
) -> Result<Value, DesktopHostError> {
    if !token(&revision_id) || pair_index > 6 {
        return Err(InspectorError::invalid_request().into());
    }
    let resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    let expected_revision = revision_id.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        bridge.request(&revision_id, pair_index, resource_dir.as_deref())
    })
    .await
    .map_err(|_| {
        DesktopHostError::new(
            "desktop_transition_inspector_task_failed",
            "The transition inspection task failed.",
        )
    })?
    .map_err(DesktopHostError::from)?;
    if !validate_response(&result, &expected_revision, pair_index) {
        return Err(InspectorError::invalid_response().into());
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validation_rejects_authority_escalation_and_unknown_fields() {
        let mut value = json!({
            "schema":"applaylist-desktop-transition-inspection-r1",
            "revision_id":"prv_abc",
            "playlist_id":"plr_abc",
            "revision_index":1,
            "pair_index":0,
            "source":{"order_index":0,"track_id":"trk_a","display_name":"A","locked":false},
            "target":{"order_index":1,"track_id":"trk_b","display_name":"B","locked":true},
            "available_snapshots":[],
            "personal_dj_model_training_authorized":false,
            "production_activation_authorized":false,
            "transition_recomputation_authorized":false,
            "playlist_mutation_authorized":false,
            "state":"missing",
            "selected_snapshot_id":null,
            "assessment":null
        });
        assert!(validate_response(&value, "prv_abc", 0));
        value["transition_recomputation_authorized"] = Value::Bool(true);
        assert!(!validate_response(&value, "prv_abc", 0));
        value["transition_recomputation_authorized"] = Value::Bool(false);
        value["source_path"] = Value::String("/tmp/audio.wav".into());
        assert!(!validate_response(&value, "prv_abc", 0));
    }
}
