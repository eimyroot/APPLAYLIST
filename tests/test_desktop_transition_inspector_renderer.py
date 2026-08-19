from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "desktop" / "host-proof" / "index.html"
JS = ROOT / "desktop" / "host-proof" / "transition-inspector.js"
BUILD_RS = ROOT / "src-tauri" / "build.rs"
LIB_RS = ROOT / "src-tauri" / "src" / "lib.rs"
RUST = ROOT / "src-tauri" / "src" / "transition_inspector.rs"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "main-transition-inspector.json"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"


def test_transition_inspector_renderer_is_external_dom_safe_and_read_only() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")

    assert '<script src="./transition-inspector.js" defer></script>' in html
    assert html.index('src="./transition-inspector.js"') < html.index('src="./playlist-editor.js"')
    for required in (
        'id="transition-inspector"',
        'id="transition-inspector-revision"',
        'id="transition-inspector-pair"',
        'id="transition-inspector-load"',
        'id="transition-inspector-result"',
    ):
        assert required in html

    assert 'originalInvoke("playlist_transition_inspect", {' in js
    assert "playlist_editor_history" in js
    assert "pairIndex" in js
    assert "transition_recomputation_authorized !== false" in js
    assert "playlist_mutation_authorized !== false" in js
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
        "/v1/playlist/transition/",
        "X-APPLAYLIST-Sidecar-Secret",
        "X-APPLAYLIST-Readiness-Nonce",
        "127.0.0.1",
        "payload_json",
        "content_utf8",
        "source_path",
        "target_path",
    ):
        assert forbidden not in js


def test_transition_inspector_tauri_surface_is_separate_and_narrow() -> None:
    build_rs = BUILD_RS.read_text(encoding="utf-8")
    lib_rs = LIB_RS.read_text(encoding="utf-8")
    rust = RUST.read_text(encoding="utf-8")
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))

    assert '"playlist_transition_inspect"' in build_rs
    assert "transition_inspector::playlist_transition_inspect" in lib_rs
    assert ".manage(TransitionInspectorBridge::from_environment())" in lib_rs
    assert capability["permissions"] == [
        "core:default",
        "allow-playlist-transition-inspect",
    ]
    assert "main-transition-inspector" in conf["app"]["security"]["capabilities"]
    assert "connect-src 'none'" in conf["app"]["security"]["csp"]

    assert '"/v1/playlist/transition/inspect"' in rust
    assert 'BUNDLED_SIDECAR_RESOURCE: &str = "applaylist-sidecar/applaylist-sidecar"' in rust
    assert "stderr(Stdio::null())" in rust
    assert "validate_response" in rust
    assert "transition_recomputation_authorized" in rust
    assert "playlist_mutation_authorized" in rust
    assert "blocking_save_file" not in rust
    assert "write_atomic" not in rust
