from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "desktop" / "host-proof" / "index.html"
APP_JS = ROOT / "desktop" / "host-proof" / "app.js"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "main-library-root.json"


def test_renderer_uses_external_script_and_safe_dom_sinks() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    assert '<script src="./app.js" defer></script>' in html
    assert "<script>" not in html
    assert ".innerHTML" not in js
    assert "insertAdjacentHTML" not in js
    assert ".textContent" in js


def test_renderer_invokes_only_authorized_library_commands() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    commands = set(re.findall(r'invoke\("([^"]+)"', js))

    assert commands == {"library_choose_root", "library_import_root"}
    assert 'invoke("library_import_root", { capabilityId })' in js
    assert "const capabilityId = selectedCapability.capability_id;" in js
    assert "selectedLibrary.textContent = capability.display_name;" in js
    assert "selectedLibrary.textContent = capability.capability_id;" not in js

    choose_body = js.split("async function chooseLibrary()", 1)[1].split(
        "async function importLibrary()", 1
    )[0]
    assert 'invoke("library_choose_root")' in choose_body
    assert 'invoke("library_import_root"' not in choose_body


def test_renderer_prevents_duplicate_actions_and_handles_cancel() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    assert 'if (busy || typeof invoke !== "function")' in js
    assert "importButton.disabled = nextBusy || selectedCapability === null;" in js
    assert "if (capability === null)" in js
    assert 'setStatus("Selection cancelled.");' in js


def test_renderer_has_no_network_shell_or_filesystem_authority() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "__TAURI__.fs",
        "__TAURI__.shell",
        "__TAURI__.http",
        "plugin:fs",
        "plugin:shell",
    ):
        assert forbidden not in js

    assert "window.__TAURI__?.core?.invoke" in js


def test_tauri_global_api_and_capability_surface_are_narrow() -> None:
    conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))

    assert conf["app"]["withGlobalTauri"] is True
    assert conf["app"]["security"]["csp"] == (
        "default-src 'self'; connect-src 'none'; img-src 'self' data:; "
        "style-src 'self'; script-src 'self'; object-src 'none'; frame-src 'none'; "
        "base-uri 'none'; form-action 'none'"
    )
    assert capability["permissions"] == [
        "allow-library-choose-root",
        "allow-library-import-root",
    ]
