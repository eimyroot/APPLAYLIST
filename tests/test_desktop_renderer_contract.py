from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "desktop" / "host-proof" / "index.html"
APP_JS = ROOT / "desktop" / "host-proof" / "app.js"
APP_CSS = ROOT / "desktop" / "host-proof" / "app.css"
TAURI_CONF = ROOT / "src-tauri" / "tauri.conf.json"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "main-library-root.json"


def test_renderer_uses_external_assets_and_safe_dom_sinks() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    css = APP_CSS.read_text(encoding="utf-8")

    assert '<script src="./app.js" defer></script>' in html
    assert '<link rel="stylesheet" href="./app.css">' in html
    assert "<script>" not in html
    assert "<style" not in html
    assert css.strip()
    assert ".innerHTML" not in js
    assert "insertAdjacentHTML" not in js
    assert "document.createElement" in js
    assert ".replaceChildren()" in js
    assert ".textContent" in js


def test_renderer_invokes_only_authorized_library_commands() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    commands = set(re.findall(r'invoke\("([^"]+)"', js))

    assert commands == {
        "library_choose_root",
        "library_import_start",
        "library_import_status",
        "library_import_cancel",
    }
    assert 'invoke("library_import_root"' not in js
    assert 'invoke("library_import_start", { capabilityId })' in js
    assert 'invoke("library_import_status", {' in js
    assert 'invoke("library_import_cancel", {' in js
    assert "const capabilityId = selectedCapability.capability_id;" in js
    assert "selectedLibrary.textContent = capability.display_name;" in js
    assert "selectedLibrary.textContent = capability.capability_id;" not in js

    choose_body = js.split("async function chooseLibrary()", 1)[1].split(
        "async function pollImport", 1
    )[0]
    assert 'invoke("library_choose_root")' in choose_body
    assert 'invoke("library_import_start"' not in choose_body


def test_renderer_prevents_duplicate_actions_and_supports_bounded_cancel() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    assert 'id="cancel-import"' in html
    assert 'if (busy || typeof invoke !== "function")' in js
    assert "importButton.disabled = busy || selectedCapability === null;" in js
    assert "cancelButton.disabled = !busy || activeJobId === null || cancelRequested;" in js
    assert 'importSection.setAttribute("aria-busy", busy ? "true" : "false");' in js
    assert "if (capability === null)" in js
    assert 'setStatus("Selection cancelled.");' in js
    assert "const POLL_INTERVAL_MS = 250;" in js
    assert "await delay(POLL_INTERVAL_MS);" in js
    assert "countsDoNotRegress(snapshot.counts, next.counts)" in js
    assert "snapshot.import_job_id !== activeJobId" in js


def test_renderer_validates_and_renders_bounded_job_and_library_read_models() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    for required_id in (
        'id="import-progress"',
        'id="progress-phase"',
        'id="progress-discovered"',
        'id="progress-accepted"',
        'id="progress-imported"',
        'id="progress-persisted"',
        'id="library-results"',
        'id="library-empty"',
        'id="library-table"',
        'id="library-rows"',
        'id="import-issues"',
        'id="issue-list"',
    ):
        assert required_id in html

    assert "/^lij_[0-9a-f]{32}$/" in js
    assert "JOB_STATES.has(value.state)" in js
    assert "JOB_PHASES.has(value.phase)" in js
    assert "TERMINAL_STATES.has(value.state)" in js
    assert "validCounts(value.counts)" in js
    assert "Array.isArray(value.tracks)" in js
    assert "value.tracks.every(validTrack)" in js
    assert "value.issues.every(validIssue)" in js
    assert "renderProgress(snapshot);" in js
    assert "renderLibraryTracks(result.tracks);" in js
    assert "renderIssues(result.issues);" in js
    assert "track.title || track.file_name" in js
    assert "displayFormat(track.file_name)" in js
    assert "displayDuration(track.duration_seconds)" in js
    assert 'track.relinked ? "Relinked" : "Imported"' in js
    assert "track.metadata_origin" in js
    assert "issue.file_name" in js
    assert ".path" not in js
    assert "absolute_path" not in js
    assert "process_id" not in js
    assert "nonce_sha256" not in js


def test_renderer_has_accessible_table_progress_and_status_regions() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-busy="false"' in html
    assert "<caption>Imported library tracks</caption>" in html
    assert html.count('scope="col"') == 6
    assert 'aria-labelledby="import-progress-heading"' in html


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
        "allow-library-import-start",
        "allow-library-import-status",
        "allow-library-import-cancel",
    ]