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

use serde::{Deserialize, Serialize};
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
const MIN_SCOPE_TRACKS: usize = 3;
const MAX_SCOPE_TRACKS: usize = 24;
const MIN_TARGET_TRACKS: usize = 3;
const MAX_TARGET_TRACKS: usize = 8;
const MAX_TRACK_ID_CHARS: usize = 256;
const MAX_DISPLAY_NAME_CHARS: usize = 512;

#[derive(Debug, Clone)]
pub struct SetProposalBridge {
    executable: Option<PathBuf>,
}

impl SetProposalBridge {
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
    ) -> Result<PathBuf, SetProposalBridgeError> {
        if let Some(configured) = self.executable.as_ref() {
            let canonical = configured
                .canonicalize()
                .map_err(|_| SetProposalBridgeError::executable_unavailable())?;
            if !canonical.is_file() {
                return Err(SetProposalBridgeError::executable_unavailable());
            }
            return Ok(canonical);
        }

        let resource_dir =
            bundled_resource_dir.ok_or_else(SetProposalBridgeError::not_configured)?;
        let canonical_resource_dir = resource_dir
            .canonicalize()
            .map_err(|_| SetProposalBridgeError::executable_unavailable())?;
        let canonical = canonical_resource_dir
            .join(BUNDLED_SIDECAR_RESOURCE)
            .canonicalize()
            .map_err(|_| SetProposalBridgeError::executable_unavailable())?;
        if !canonical.starts_with(&canonical_resource_dir) || !canonical.is_file() {
            return Err(SetProposalBridgeError::executable_unavailable());
        }
        Ok(canonical)
    }

    fn generate_with_resource_dir(
        &self,
        track_ids: &[String],
        seed_track_id: &str,
        target_track_count: usize,
        bundled_resource_dir: Option<&Path>,
    ) -> Result<DesktopSetProposalDto, SetProposalBridgeError> {
        validate_request(track_ids, seed_track_id, target_track_count)?;
        let executable = self.configured_executable(bundled_resource_dir)?;
        let mut session = SetProposalSidecarSession::connect(&executable)?;
        let body = serde_json::to_vec(&SetProposalRequest {
            track_ids,
            seed_track_id,
            target_track_count,
        })
        .map_err(|_| SetProposalBridgeError::request_encoding_failed())?;

        let response = session.post("/v1/set/proposal/generate", &body);
        let result = match response {
            Ok((200, response_body)) => parse_set_proposal(&response_body),
            Ok((status, response_body)) => {
                let sidecar_error = parse_sidecar_error(&response_body);
                Err(SetProposalBridgeError::proposal_rejected(
                    status,
                    sidecar_error.as_deref(),
                ))
            }
            Err(error) => Err(error),
        };
        session.shutdown();
        result
    }
}

impl Default for SetProposalBridge {
    fn default() -> Self {
        Self::from_environment()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct SetProposalBridgeError {
    code: &'static str,
    message: &'static str,
}

impl SetProposalBridgeError {
    const fn new(code: &'static str, message: &'static str) -> Self {
        Self { code, message }
    }

    const fn not_configured() -> Self {
        Self::new(
            "desktop_set_proposal_sidecar_not_configured",
            "The desktop set proposal service is not configured.",
        )
    }

    const fn executable_unavailable() -> Self {
        Self::new(
            "desktop_set_proposal_sidecar_unavailable",
            "The desktop set proposal service is unavailable.",
        )
    }

    const fn startup_failed() -> Self {
        Self::new(
            "desktop_set_proposal_sidecar_startup_failed",
            "The desktop set proposal service could not start.",
        )
    }

    const fn readiness_failed() -> Self {
        Self::new(
            "desktop_set_proposal_sidecar_readiness_failed",
            "The desktop set proposal service did not become ready.",
        )
    }

    const fn authentication_failed() -> Self {
        Self::new(
            "desktop_set_proposal_sidecar_authentication_failed",
            "The desktop set proposal service authentication failed.",
        )
    }

    const fn request_failed() -> Self {
        Self::new(
            "desktop_set_proposal_request_failed",
            "The desktop set proposal request failed.",
        )
    }

    const fn request_encoding_failed() -> Self {
        Self::new(
            "desktop_set_proposal_request_encoding_failed",
            "The desktop set proposal request could not be encoded.",
        )
    }

    const fn invalid_request() -> Self {
        Self::new(
            "invalid_desktop_set_proposal_request",
            "The desktop set proposal request is invalid.",
        )
    }

    const fn invalid_response() -> Self {
        Self::new(
            "desktop_set_proposal_response_invalid",
            "The desktop set proposal response was invalid.",
        )
    }

    fn proposal_rejected(status: u16, error: Option<&str>) -> Self {
        match (status, error) {
            (409, Some("set_proposal_analysis_missing")) => Self::new(
                "desktop_set_proposal_analysis_missing",
                "One or more selected tracks have no analysis evidence.",
            ),
            (409, Some("set_proposal_analysis_failed")) => Self::new(
                "desktop_set_proposal_analysis_failed",
                "One or more selected tracks have a failed latest analysis.",
            ),
            (409, Some("set_proposal_analysis_incomplete")) => Self::new(
                "desktop_set_proposal_analysis_incomplete",
                "One or more selected tracks lack required proposal evidence.",
            ),
            (409, Some("set_proposal_track_unavailable")) => Self::new(
                "desktop_set_proposal_track_unavailable",
                "One or more selected tracks are unavailable in the local library.",
            ),
            (400, Some("invalid_set_proposal_request")) => Self::invalid_request(),
            _ => Self::new(
                "desktop_set_proposal_rejected",
                "The desktop set proposal request was rejected.",
            ),
        }
    }
}

impl From<SetProposalBridgeError> for DesktopHostError {
    fn from(value: SetProposalBridgeError) -> Self {
        DesktopHostError::new(value.code, value.message)
    }
}

#[derive(Debug, Serialize)]
struct SetProposalRequest<'a> {
    track_ids: &'a [String],
    seed_track_id: &'a str,
    target_track_count: usize,
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

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SidecarError {
    error: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct DesktopSetProposalDto {
    schema: String,
    proposal_id: String,
    status: String,
    alternatives: Vec<DesktopSetProposalAlternativeDto>,
    reason_codes: Vec<String>,
    warning_codes: Vec<String>,
    budget_exhausted: bool,
    missing_evidence_detected: bool,
    deterministic_ordering: bool,
    activation_authorized: bool,
    personal_dj_model_training_authorized: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct DesktopSetProposalAlternativeDto {
    path_id: String,
    rank: usize,
    sequence: Vec<DesktopSetProposalStepDto>,
    transition_ids: Vec<String>,
    candidate_scores: Vec<f64>,
    objective: DesktopSetProposalObjectiveDto,
    explanation_codes: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct DesktopSetProposalStepDto {
    order_index: usize,
    track_id: String,
    display_name: String,
    phase_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct DesktopSetProposalObjectiveDto {
    depth: usize,
    mean_candidate_score: f64,
    minimum_candidate_score: f64,
    required_track_completion: f64,
    remaining_required_count: usize,
    target_reached: bool,
}

struct SetProposalSidecarSession {
    child: Child,
    port: u16,
    secret: String,
    nonce: String,
}

impl SetProposalSidecarSession {
    fn connect(executable: &Path) -> Result<Self, SetProposalBridgeError> {
        let secret = random_token();
        let nonce = random_token();
        let mut child = spawn_sidecar(executable, &secret, &nonce)?;
        let ready = read_ready(&mut child)?;
        validate_ready(&ready, &nonce)?;
        verify_health(ready.port, &secret, &nonce)?;
        Ok(Self {
            child,
            port: ready.port,
            secret,
            nonce,
        })
    }

    fn post(&mut self, path: &str, body: &[u8]) -> Result<(u16, Vec<u8>), SetProposalBridgeError> {
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

    fn shutdown(&mut self) {
        let _ = request_json(
            self.port,
            "POST",
            "/v1/shutdown",
            &self.secret,
            &self.nonce,
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

impl Drop for SetProposalSidecarSession {
    fn drop(&mut self) {
        if matches!(self.child.try_wait(), Ok(None)) {
            let _ = self.child.kill();
        }
        let _ = self.child.wait();
    }
}

fn spawn_sidecar(
    executable: &Path,
    secret: &str,
    nonce: &str,
) -> Result<Child, SetProposalBridgeError> {
    let mut child = Command::new(executable)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| SetProposalBridgeError::startup_failed())?;
    let envelope = serde_json::to_vec(&serde_json::json!({
        "protocol": PROTOCOL_VERSION,
        "secret": secret,
        "nonce": nonce,
    }))
    .map_err(|_| SetProposalBridgeError::startup_failed())?;
    let mut stdin = child
        .stdin
        .take()
        .ok_or_else(SetProposalBridgeError::startup_failed)?;
    stdin
        .write_all(&envelope)
        .and_then(|_| stdin.write_all(b"\n"))
        .and_then(|_| stdin.flush())
        .map_err(|_| SetProposalBridgeError::startup_failed())?;
    drop(stdin);
    Ok(child)
}

fn read_ready(child: &mut Child) -> Result<SidecarReady, SetProposalBridgeError> {
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(SetProposalBridgeError::readiness_failed)?;
    let (sender, receiver) = mpsc::sync_channel(1);
    thread::spawn(move || {
        let result = read_bounded_line(&mut stdout, MAX_READY_BYTES);
        let _ = sender.send(result);
    });
    let line = receiver
        .recv_timeout(READY_TIMEOUT)
        .map_err(|_| SetProposalBridgeError::readiness_failed())?
        .map_err(|_| SetProposalBridgeError::readiness_failed())?;
    serde_json::from_slice(&line).map_err(|_| SetProposalBridgeError::readiness_failed())
}

fn validate_request(
    track_ids: &[String],
    seed_track_id: &str,
    target_track_count: usize,
) -> Result<(), SetProposalBridgeError> {
    if track_ids.len() < MIN_SCOPE_TRACKS || track_ids.len() > MAX_SCOPE_TRACKS {
        return Err(SetProposalBridgeError::invalid_request());
    }
    let mut unique = HashSet::with_capacity(track_ids.len());
    for track_id in track_ids {
        validate_track_id(track_id)?;
        if !unique.insert(track_id.as_str()) {
            return Err(SetProposalBridgeError::invalid_request());
        }
    }
    validate_track_id(seed_track_id)?;
    if !unique.contains(seed_track_id) {
        return Err(SetProposalBridgeError::invalid_request());
    }
    if target_track_count < MIN_TARGET_TRACKS
        || target_track_count > MAX_TARGET_TRACKS
        || target_track_count > track_ids.len()
    {
        return Err(SetProposalBridgeError::invalid_request());
    }
    Ok(())
}

fn validate_track_id(track_id: &str) -> Result<(), SetProposalBridgeError> {
    if track_id.is_empty()
        || track_id.len() > MAX_TRACK_ID_CHARS
        || track_id.trim() != track_id
        || track_id.contains('/')
        || track_id.contains('\\')
        || track_id.chars().any(char::is_control)
    {
        return Err(SetProposalBridgeError::invalid_request());
    }
    Ok(())
}

fn parse_set_proposal(body: &[u8]) -> Result<DesktopSetProposalDto, SetProposalBridgeError> {
    let proposal = serde_json::from_slice::<DesktopSetProposalDto>(body)
        .map_err(|_| SetProposalBridgeError::invalid_response())?;
    validate_set_proposal(&proposal)?;
    Ok(proposal)
}

fn validate_set_proposal(proposal: &DesktopSetProposalDto) -> Result<(), SetProposalBridgeError> {
    if proposal.schema != "applaylist-desktop-set-proposal-r1"
        || !safe_token(&proposal.proposal_id, 256)
        || !matches!(
            proposal.status.as_str(),
            "target_reached"
                | "paths_found"
                | "no_eligible_path"
                | "not_proven_missing_evidence"
                | "budget_exhausted"
        )
        || !proposal.deterministic_ordering
        || proposal.activation_authorized
        || proposal.personal_dj_model_training_authorized
        || proposal.alternatives.len() > 3
    {
        return Err(SetProposalBridgeError::invalid_response());
    }
    validate_codes(&proposal.reason_codes)?;
    validate_codes(&proposal.warning_codes)?;

    for (index, alternative) in proposal.alternatives.iter().enumerate() {
        if alternative.rank != index + 1
            || !safe_token(&alternative.path_id, 256)
            || alternative.sequence.len() < 2
            || alternative.sequence.len() > MAX_TARGET_TRACKS
            || alternative.transition_ids.len() != alternative.candidate_scores.len()
            || alternative.sequence.len() != alternative.candidate_scores.len() + 1
            || alternative.objective.depth != alternative.candidate_scores.len()
        {
            return Err(SetProposalBridgeError::invalid_response());
        }
        validate_codes(&alternative.explanation_codes)?;
        for (step_index, step) in alternative.sequence.iter().enumerate() {
            if step.order_index != step_index
                || validate_track_id(&step.track_id).is_err()
                || !safe_display_name(&step.display_name)
                || !safe_token(&step.phase_id, 256)
            {
                return Err(SetProposalBridgeError::invalid_response());
            }
        }
        if alternative
            .transition_ids
            .iter()
            .any(|value| !safe_token(value, 256))
            || alternative
                .candidate_scores
                .iter()
                .any(|value| !unit_number(*value))
            || !unit_number(alternative.objective.mean_candidate_score)
            || !unit_number(alternative.objective.minimum_candidate_score)
            || !unit_number(alternative.objective.required_track_completion)
            || alternative.objective.remaining_required_count > MAX_SCOPE_TRACKS
        {
            return Err(SetProposalBridgeError::invalid_response());
        }
    }

    if matches!(proposal.status.as_str(), "target_reached" | "paths_found")
        && proposal.alternatives.is_empty()
    {
        return Err(SetProposalBridgeError::invalid_response());
    }
    if proposal.status == "no_eligible_path" && !proposal.alternatives.is_empty() {
        return Err(SetProposalBridgeError::invalid_response());
    }
    Ok(())
}

fn validate_codes(values: &[String]) -> Result<(), SetProposalBridgeError> {
    if values.len() > 128 || values.iter().any(|value| !safe_token(value, 128)) {
        return Err(SetProposalBridgeError::invalid_response());
    }
    Ok(())
}

fn safe_token(value: &str, maximum: usize) -> bool {
    if value.is_empty() || value.len() > maximum || value.trim() != value {
        return false;
    }
    value.chars().enumerate().all(|(index, character)| {
        character.is_ascii_alphanumeric()
            || (index > 0 && matches!(character, '_' | '.' | ':' | '+' | '-'))
    })
}

fn safe_display_name(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_DISPLAY_NAME_CHARS
        && value.trim() == value
        && !value.chars().any(char::is_control)
        && !looks_like_absolute_path(value)
}

fn unit_number(value: f64) -> bool {
    value.is_finite() && (0.0..=1.0).contains(&value)
}

fn looks_like_absolute_path(value: &str) -> bool {
    if value.starts_with('/') || value.starts_with("\\\\") {
        return true;
    }
    let bytes = value.as_bytes();
    bytes.len() >= 3
        && bytes[0].is_ascii_alphabetic()
        && bytes[1] == b':'
        && (bytes[2] == b'\\' || bytes[2] == b'/')
}

fn parse_sidecar_error(body: &[u8]) -> Option<String> {
    let error = serde_json::from_slice::<SidecarError>(body).ok()?;
    safe_token(&error.error, 128).then_some(error.error)
}

fn random_token() -> String {
    format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple())
}

fn sha256_hex(value: &str) -> String {
    format!("{:x}", Sha256::digest(value.as_bytes()))
}

fn validate_ready(ready: &SidecarReady, nonce: &str) -> Result<(), SetProposalBridgeError> {
    if ready.event != "ready"
        || ready.protocol != PROTOCOL_VERSION
        || ready.host != "127.0.0.1"
        || ready.port == 0
        || ready.process_id == 0
        || ready.nonce_sha256 != sha256_hex(nonce)
    {
        return Err(SetProposalBridgeError::readiness_failed());
    }
    Ok(())
}

fn verify_health(port: u16, secret: &str, nonce: &str) -> Result<(), SetProposalBridgeError> {
    let (status, body) =
        request_json(port, "GET", "/v1/health", secret, nonce, None, HTTP_TIMEOUT)?;
    if status == 401 {
        return Err(SetProposalBridgeError::authentication_failed());
    }
    if status != 200 {
        return Err(SetProposalBridgeError::request_failed());
    }
    let health = serde_json::from_slice::<HealthResponse>(&body)
        .map_err(|_| SetProposalBridgeError::readiness_failed())?;
    if health.status != "ready"
        || health.protocol != PROTOCOL_VERSION
        || health.nonce_sha256 != sha256_hex(nonce)
    {
        return Err(SetProposalBridgeError::readiness_failed());
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
) -> Result<(u16, Vec<u8>), SetProposalBridgeError> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, HTTP_TIMEOUT)
        .map_err(|_| SetProposalBridgeError::request_failed())?;
    stream
        .set_read_timeout(Some(read_timeout))
        .and_then(|_| stream.set_write_timeout(Some(HTTP_TIMEOUT)))
        .map_err(|_| SetProposalBridgeError::request_failed())?;

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
        .map_err(|_| SetProposalBridgeError::request_failed())?;

    let mut response = Vec::new();
    stream
        .take(MAX_HTTP_RESPONSE_BYTES + 1)
        .read_to_end(&mut response)
        .map_err(|_| SetProposalBridgeError::request_failed())?;
    if response.len() as u64 > MAX_HTTP_RESPONSE_BYTES {
        return Err(SetProposalBridgeError::request_failed());
    }
    parse_http_response(&response)
}

fn parse_http_response(response: &[u8]) -> Result<(u16, Vec<u8>), SetProposalBridgeError> {
    let boundary = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(SetProposalBridgeError::request_failed)?;
    let headers = std::str::from_utf8(&response[..boundary])
        .map_err(|_| SetProposalBridgeError::request_failed())?;
    let mut lines = headers.split("\r\n");
    let status_line = lines
        .next()
        .ok_or_else(SetProposalBridgeError::request_failed)?;
    let mut status_parts = status_line.split_whitespace();
    if status_parts.next() != Some("HTTP/1.1") {
        return Err(SetProposalBridgeError::request_failed());
    }
    let status = status_parts
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(SetProposalBridgeError::request_failed)?;
    let mut content_length = None;
    for line in lines {
        let Some((name, value)) = line.split_once(':') else {
            return Err(SetProposalBridgeError::request_failed());
        };
        if name.eq_ignore_ascii_case("Content-Length") {
            content_length = value.trim().parse::<usize>().ok();
        }
    }
    let body = &response[boundary + 4..];
    if content_length != Some(body.len()) {
        return Err(SetProposalBridgeError::request_failed());
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

#[tauri::command]
pub async fn set_proposal_generate(
    track_ids: Vec<String>,
    seed_track_id: String,
    target_track_count: usize,
    bridge: State<'_, SetProposalBridge>,
    app: AppHandle,
) -> Result<DesktopSetProposalDto, DesktopHostError> {
    validate_request(&track_ids, &seed_track_id, target_track_count)
        .map_err(DesktopHostError::from)?;
    let bundled_resource_dir = app.path().resource_dir().ok();
    let bridge = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        bridge.generate_with_resource_dir(
            &track_ids,
            &seed_track_id,
            target_track_count,
            bundled_resource_dir.as_deref(),
        )
    })
    .await
    .map_err(|_| {
        DesktopHostError::new(
            "desktop_set_proposal_task_failed",
            "The desktop set proposal task failed.",
        )
    })?
    .map_err(DesktopHostError::from)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn safe_fixture() -> Vec<u8> {
        br#"{
          "schema":"applaylist-desktop-set-proposal-r1",
          "proposal_id":"sor_0123456789abcdef",
          "status":"target_reached",
          "alternatives":[{
            "path_id":"sp_0123456789abcdef",
            "rank":1,
            "sequence":[
              {"order_index":0,"track_id":"track:a","display_name":"A","phase_id":"phase:preview-groove"},
              {"order_index":1,"track_id":"track:b","display_name":"B","phase_id":"phase:preview-groove"},
              {"order_index":2,"track_id":"track:c","display_name":"C","phase_id":"phase:preview-groove"}
            ],
            "transition_ids":["ta_a","ta_b"],
            "candidate_scores":[0.8,0.7],
            "objective":{
              "depth":2,
              "mean_candidate_score":0.75,
              "minimum_candidate_score":0.7,
              "required_track_completion":1.0,
              "remaining_required_count":0,
              "target_reached":true
            },
            "explanation_codes":["bounded_beam_lookahead_v1"]
          }],
          "reason_codes":["deterministic_bounded_beam_search_v1"],
          "warning_codes":["future_feasibility_not_hard_prune_v1"],
          "budget_exhausted":false,
          "missing_evidence_detected":false,
          "deterministic_ordering":true,
          "activation_authorized":false,
          "personal_dj_model_training_authorized":false
        }"#
        .to_vec()
    }

    #[test]
    fn request_validation_is_bounded_and_path_safe() {
        let tracks = vec![
            "aptrack:v1:sha256:aaa".to_owned(),
            "aptrack:v1:sha256:bbb".to_owned(),
            "aptrack:v1:sha256:ccc".to_owned(),
        ];
        assert!(validate_request(&tracks, &tracks[0], 3).is_ok());
        assert!(validate_request(&tracks, "/Users/example/a.wav", 3).is_err());
        assert!(validate_request(&tracks, &tracks[0], 9).is_err());
    }

    #[test]
    fn proposal_parser_rejects_unknown_fields_and_authority_escalation() {
        let safe = safe_fixture();
        assert!(parse_set_proposal(&safe).is_ok());

        let escalation = String::from_utf8(safe.clone()).expect("utf8").replace(
            "\"activation_authorized\":false",
            "\"activation_authorized\":true",
        );
        assert!(parse_set_proposal(escalation.as_bytes()).is_err());

        let unknown = String::from_utf8(safe)
            .expect("utf8")
            .replace("\"schema\":", "\"path\":\"/tmp/a.wav\",\"schema\":");
        assert!(parse_set_proposal(unknown.as_bytes()).is_err());
    }
}
