from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR_JS = ROOT / "desktop" / "host-proof" / "playlist-editor.js"
RUST = ROOT / "src-tauri" / "src" / "playlist_regeneration.rs"
BUILD = ROOT / "src-tauri" / "build.rs"
LIB = ROOT / "src-tauri" / "src" / "lib.rs"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "main-playlist-regeneration.json"
CONFIG = ROOT / "src-tauri" / "tauri.conf.json"
SIDECAR = ROOT / "services" / "desktop" / "playlist_editor_sidecar.py"


def test_regeneration_renderer_is_explicit_dom_safe_and_path_free() -> None:
    editor = EDITOR_JS.read_text(encoding="utf-8")

    assert "playlist_editor_regeneration_preview" in editor
    assert "playlist_editor_regeneration_apply" in editor
    assert "applaylist-desktop-playlist-regeneration-r1" in editor
    assert '"regenerate"' in editor
    assert "Regenerate around locks" in editor
    assert "position 1 must be locked" in editor.lower()
    assert "document.createElement" in editor
    assert ".textContent" in editor
    assert "innerHTML" not in editor
    assert "insertAdjacentHTML" not in editor
    assert "fetch(" not in editor
    assert "XMLHttpRequest" not in editor
    assert "WebSocket" not in editor
    assert "localStorage" not in editor
    assert "sessionStorage" not in editor
    for forbidden in (
        "/v1/playlist/editor/regeneration/",
        "X-APPLAYLIST-Sidecar-Secret",
        "X-APPLAYLIST-Readiness-Nonce",
        "127.0.0.1",
        "payload_json",
        "content_utf8",
        "filesystem_path",
    ):
        assert forbidden not in editor


def test_regeneration_tauri_surface_is_narrow_and_separate() -> None:
    rust = RUST.read_text(encoding="utf-8")
    build = BUILD.read_text(encoding="utf-8")
    lib = LIB.read_text(encoding="utf-8")
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    sidecar = SIDECAR.read_text(encoding="utf-8")

    commands = (
        "playlist_editor_regeneration_preview",
        "playlist_editor_regeneration_apply",
    )
    for command in commands:
        assert command in rust
        assert command in build
        assert command in lib
    assert capability["permissions"] == [
        "core:default",
        "allow-playlist-editor-regeneration-preview",
        "allow-playlist-editor-regeneration-apply",
    ]
    assert "main-playlist-regeneration" in config["app"]["security"]["capabilities"]
    assert "connect-src 'none'" in config["app"]["security"]["csp"]

    assert '"/v1/playlist/editor/regeneration/preview"' in rust
    assert '"/v1/playlist/editor/regeneration/apply"' in rust
    assert '"/v1/playlist/editor/regeneration/preview"' in sidecar
    assert '"/v1/playlist/editor/regeneration/apply"' in sidecar
    assert "blocking_save_file" not in rust
    assert "write_atomic" not in rust
    assert "tauri_plugin_fs" not in rust


def test_existing_revision_consumers_accept_regenerated_history() -> None:
    for relative in (
        "desktop/host-proof/playlist-editor.js",
        "desktop/host-proof/playlist-export.js",
        "desktop/host-proof/playlist-evidence-export.js",
        "desktop/host-proof/transition-inspector.js",
    ):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert '"regenerate"' in content
