from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "desktop" / "host-proof" / "index.html"
JS = ROOT / "desktop" / "host-proof" / "playlist-evidence-export.js"
BUILD_RS = ROOT / "src-tauri" / "build.rs"
LIB_RS = ROOT / "src-tauri" / "src" / "lib.rs"
RUST = ROOT / "src-tauri" / "src" / "playlist_evidence_export.rs"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "main-playlist-evidence-export.json"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"


def test_playlist_evidence_renderer_is_external_strict_and_path_safe() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")

    assert '<script src="./playlist-evidence-export.js" defer></script>' in html
    for required in (
        'id="playlist-evidence-export"',
        'id="playlist-evidence-revision"',
        'id="playlist-evidence-preview"',
        'id="playlist-evidence-write"',
        'id="playlist-evidence-preview-result"',
        'id="playlist-evidence-receipt"',
    ):
        assert required in html

    assert 'originalInvoke("playlist_evidence_preview", {' in js
    assert 'originalInvoke("playlist_evidence_export_json", {' in js
    assert "applaylist-desktop-playlist-evidence-preview-r1" in js
    assert "m3u8_path_valid === true" in js
    assert "validDigest" in js
    assert "exactKeys" in js
    assert "document.createElement" in js
    assert ".textContent" in js
    assert ".innerHTML" not in js
    assert "insertAdjacentHTML" not in js

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "__TAURI__.fs",
        "__TAURI__.shell",
        "__TAURI__.http",
        "plugin:fs",
        "plugin:shell",
        "/v1/playlist/evidence/",
        "X-APPLAYLIST-Sidecar-Secret",
        "X-APPLAYLIST-Readiness-Nonce",
        "127.0.0.1",
        "content_utf8",
        "source_path",
        "output_path",
    ):
        assert forbidden not in js


def test_playlist_evidence_tauri_surface_is_separate_and_narrow() -> None:
    build_rs = BUILD_RS.read_text(encoding="utf-8")
    lib_rs = LIB_RS.read_text(encoding="utf-8")
    rust = RUST.read_text(encoding="utf-8")
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))

    for command in ("playlist_evidence_preview", "playlist_evidence_export_json"):
        assert f'"{command}"' in build_rs
        assert f"playlist_evidence_export::{command}" in lib_rs
        assert f"allow-{command.replace('_', '-')}" in capability["permissions"]

    assert ".manage(PlaylistEvidenceExportBridge::from_environment())" in lib_rs
    assert '"main-playlist-evidence-export"' in conf["app"]["security"]["capabilities"]
    assert "#[serde(deny_unknown_fields)]" in rust
    assert '"/v1/playlist/evidence/preview"' in rust
    assert '"/v1/playlist/evidence/material"' in rust
    assert "blocking_save_file" in rust
    assert "contains_forbidden_path_key" in rust
    assert 'add_filter("APPLAYLIST JSON evidence", &["json"])' in rust
    assert "personal_dj_model_training_authorized" in rust
    assert "production_activation_authorized" in rust
