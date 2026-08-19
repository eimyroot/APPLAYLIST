from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "desktop" / "host-proof" / "index.html"
JS = ROOT / "desktop" / "host-proof" / "playlist-vendor-interop.js"
BUILD_RS = ROOT / "src-tauri" / "build.rs"
LIB_RS = ROOT / "src-tauri" / "src" / "lib.rs"
RUST = ROOT / "src-tauri" / "src" / "playlist_vendor_interop.rs"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "main-playlist-vendor-interop.json"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"


def test_vendor_interop_renderer_is_external_dom_safe_and_capability_gated() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")

    assert '<script src="./playlist-vendor-interop.js" defer></script>' in html
    for required in (
        'id="playlist-vendor-interop"',
        'id="playlist-vendor-interop-revision"',
        'id="playlist-vendor-interop-preview"',
        'id="playlist-vendor-interop-rekordbox"',
        'id="playlist-vendor-interop-capabilities"',
        'id="playlist-vendor-interop-receipt"',
    ):
        assert required in html

    assert 'originalInvoke("playlist_vendor_interop_preview", {' in js
    assert 'originalInvoke("playlist_vendor_interop_export_rekordbox", {' in js
    assert "documented_format_export" in js
    assert "guidance_only_nml_required" in js
    assert "guidance_only_files_crate" in js
    assert "artifactExportAvailable: true" in js
    assert js.count("artifactExportAvailable: false") == 2
    assert "document.createElement" in js
    assert ".textContent" in js
    assert ".innerHTML" not in js
    assert "insertAdjacentHTML" not in js

    for forbidden in (
        "playlist_vendor_interop_export_traktor",
        "playlist_vendor_interop_export_serato",
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "__TAURI__.fs",
        "__TAURI__.shell",
        "__TAURI__.http",
        "plugin:fs",
        "plugin:shell",
        "/v1/playlist/vendor/",
        "X-APPLAYLIST-Sidecar-Secret",
        "X-APPLAYLIST-Readiness-Nonce",
        "127.0.0.1",
        "content_utf8",
        "file://localhost/",
    ):
        assert forbidden not in js


def test_vendor_interop_tauri_surface_is_separate_and_rekordbox_only() -> None:
    build_rs = BUILD_RS.read_text(encoding="utf-8")
    lib_rs = LIB_RS.read_text(encoding="utf-8")
    rust = RUST.read_text(encoding="utf-8")
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))

    for command in (
        "playlist_vendor_interop_preview",
        "playlist_vendor_interop_export_rekordbox",
    ):
        assert f'"{command}"' in build_rs
        assert f"playlist_vendor_interop::{command}" in lib_rs
        assert f"allow-{command.replace('_', '-')}" in capability["permissions"]

    for forbidden in (
        "playlist_vendor_interop_export_traktor",
        "playlist_vendor_interop_export_serato",
    ):
        assert forbidden not in build_rs
        assert forbidden not in lib_rs
        assert forbidden not in json.dumps(capability)

    assert capability["permissions"] == [
        "core:default",
        "allow-playlist-vendor-interop-preview",
        "allow-playlist-vendor-interop-export-rekordbox",
    ]
    assert "main-playlist-vendor-interop" in conf["app"]["security"]["capabilities"]
    assert ".manage(PlaylistVendorInteropBridge::from_environment())" in lib_rs
    assert "#[serde(deny_unknown_fields)]" in rust
    assert '"/v1/playlist/vendor/preview"' in rust
    assert '"/v1/playlist/vendor/rekordbox/material"' in rust
    assert 'add_filter("rekordbox XML", &["xml"])' in rust
    assert "blocking_save_file" in rust
    assert "write_atomic" in rust
    assert "vendor_database_mutation_authorized" in rust
    assert "personal_dj_model_training_authorized" in rust
    assert "production_activation_authorized" in rust
