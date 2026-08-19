from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "desktop" / "host-proof" / "index.html"
JS = ROOT / "desktop" / "host-proof" / "set-proposal.js"
CSS = ROOT / "desktop" / "host-proof" / "set-proposal.css"
BUILD_RS = ROOT / "src-tauri" / "build.rs"
LIB_RS = ROOT / "src-tauri" / "src" / "lib.rs"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "main-set-proposal.json"
RUST = ROOT / "src-tauri" / "src" / "set_proposal.rs"


def test_set_proposal_renderer_is_external_strict_and_dom_safe() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert '<script src="./set-proposal.js" defer></script>' in html
    assert '<link rel="stylesheet" href="./set-proposal.css">' in html
    assert css.strip()
    for required in (
        'id="set-proposal"',
        'id="set-proposal-refresh"',
        'id="set-proposal-track-list"',
        'id="set-proposal-seed"',
        'id="set-proposal-target"',
        'id="set-proposal-generate"',
        'id="set-proposal-results"',
    ):
        assert required in html

    assert ".innerHTML" not in js
    assert "insertAdjacentHTML" not in js
    assert "document.createElement" in js
    assert ".textContent" in js
    assert 'invoke("analysis_inspector_list", { filter: "all" })' in js
    assert 'invoke("set_proposal_generate", {' in js
    assert "validProposal" in js
    assert "exactKeys(value" in js
    assert 'value.schema !== "applaylist-desktop-set-proposal-r1"' in js
    assert "value.deterministic_ordering !== true" in js
    assert "value.activation_authorized !== false" in js
    assert "value.personal_dj_model_training_authorized !== false" in js


def test_set_proposal_renderer_has_no_network_filesystem_or_sidecar_authority() -> None:
    js = JS.read_text(encoding="utf-8")
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "__TAURI__.fs",
        "__TAURI__.shell",
        "__TAURI__.http",
        "plugin:fs",
        "plugin:shell",
        "/v1/set/",
        "/v1/analysis/",
        "X-APPLAYLIST-Sidecar-Secret",
        "X-APPLAYLIST-Readiness-Nonce",
        "127.0.0.1",
        "process_id",
        "nonce_sha256",
        "input_fingerprint",
        "evidence_id",
    ):
        assert forbidden not in js


def test_set_proposal_tauri_surface_is_separate_and_narrow() -> None:
    build_rs = BUILD_RS.read_text(encoding="utf-8")
    lib_rs = LIB_RS.read_text(encoding="utf-8")
    rust = RUST.read_text(encoding="utf-8")
    conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))

    assert '"set_proposal_generate"' in build_rs
    assert "set_proposal::set_proposal_generate" in lib_rs
    assert ".manage(SetProposalBridge::from_environment())" in lib_rs
    assert capability["permissions"] == ["allow-set-proposal-generate"]
    assert set(conf["app"]["security"]["capabilities"]) == {
        "main-library-root",
        "main-set-proposal",
        "main-playlist-editor",
        "main-playlist-export",
    }

    assert "#[serde(deny_unknown_fields)]" in rust
    assert '"/v1/set/proposal/generate"' in rust
    assert 'BUNDLED_SIDECAR_RESOURCE: &str = "applaylist-sidecar/applaylist-sidecar"' in rust
    assert "stderr(Stdio::null())" in rust
    assert 'ready.host != "127.0.0.1"' in rust
    assert "proposal.activation_authorized" in rust
    assert "proposal.personal_dj_model_training_authorized" in rust
