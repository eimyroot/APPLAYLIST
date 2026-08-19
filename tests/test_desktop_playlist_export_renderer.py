from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "desktop" / "host-proof" / "index.html"
JS = ROOT / "desktop" / "host-proof" / "playlist-export.js"
BUILD_RS = ROOT / "src-tauri" / "build.rs"
LIB_RS = ROOT / "src-tauri" / "src" / "lib.rs"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "main-playlist-export.json"
RUST = ROOT / "src-tauri" / "src" / "playlist_export.rs"


def test_playlist_export_renderer_is_strict_path_safe_and_dom_only() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")

    assert '<script src="./playlist-export.js" defer></script>' in html
    for required in (
        'id="playlist-export"',
        'id="playlist-export-revision"',
        'id="playlist-export-preview"',
        'id="playlist-export-write"',
        'id="playlist-export-preview-result"',
        'id="playlist-export-receipt"',
    ):
        assert required in html

    assert 'originalInvoke("playlist_export_preview", {' in js
    assert 'originalInvoke("playlist_export_m3u8", {' in js
    assert "applaylist-desktop-playlist-export-preview-r1" in js
    assert "validReceipt" in js
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
        "/v1/playlist/export/material",
        "content_utf8",
        "X-APPLAYLIST-Sidecar-Secret",
        "X-APPLAYLIST-Readiness-Nonce",
        "127.0.0.1",
        "process_id",
        "nonce_sha256",
    ):
        assert forbidden not in js


def test_playlist_export_tauri_surface_is_narrow_and_private_material_stays_in_rust() -> None:
    build = BUILD_RS.read_text(encoding="utf-8")
    lib = LIB_RS.read_text(encoding="utf-8")
    rust = RUST.read_text(encoding="utf-8")
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    config = json.loads(TAURI_CONF.read_text(encoding="utf-8"))

    for command in ("playlist_export_preview", "playlist_export_m3u8"):
        assert command in build
        assert f"playlist_export::{command}" in lib
        assert f"allow-{command.replace('_', '-')}" in capability["permissions"]

    assert ".manage(PlaylistExportBridge::from_environment())" in lib
    assert capability["permissions"] == [
        "allow-playlist-export-preview",
        "allow-playlist-export-m3u8",
    ]
    assert "main-playlist-export" in config["app"]["security"]["capabilities"]
    assert "#[serde(deny_unknown_fields)]" in rust
    assert '"/v1/playlist/export/preview"' in rust
    assert '"/v1/playlist/export/material"' in rust
    assert "blocking_save_file" in rust
    assert "write_atomic" in rust
    assert "content_utf8" in rust
    assert "PlaylistExportReceipt" in rust
    assert "personal_dj_model_training_authorized: false" in rust
    assert "production_activation_authorized: false" in rust
