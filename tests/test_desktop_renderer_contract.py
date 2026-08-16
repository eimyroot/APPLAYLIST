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
BUILD_RS = ROOT / "src-tauri" / "build.rs"
LIB_RS = ROOT / "src-tauri" / "src" / "lib.rs"
ANALYSIS_JOB_RS = ROOT / "src-tauri" / "src" / "analysis_job.rs"
ANALYSIS_BRIDGE_RS = ROOT / "src-tauri" / "src" / "analysis_bridge.rs"

EXPECTED_COMMANDS = {
    "library_choose_root",
    "library_import_start",
    "library_import_status",
    "library_import_cancel",
    "analysis_start",
    "analysis_status",
    "analysis_cancel",
    "analysis_inspector_list",
    "analysis_inspector_get",
    "analysis_correct",
    "analysis_reanalyze",
}


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


def test_renderer_invokes_only_exact_authorized_commands() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    commands = set(re.findall(r'invoke\("([^"]+)"', js))
    dynamic_commands = set(re.findall(r'runAnalysisCommand\("([^"]+)"', js))

    assert commands | dynamic_commands == EXPECTED_COMMANDS
    assert 'invoke("library_import_root"' not in js
    assert 'invoke("library_import_start", { capabilityId })' in js
    assert 'invoke("library_import_status", {' in js
    assert 'invoke("library_import_cancel", {' in js
    assert 'invoke("analysis_status", {' in js
    assert 'invoke("analysis_cancel", {' in js
    assert 'invoke("analysis_inspector_list", { filter })' in js
    assert 'invoke("analysis_inspector_get", { trackId })' in js
    assert 'invoke("analysis_correct", {' in js
    assert 'runAnalysisCommand("analysis_start", { trackIds, preferredProvider: null })' in js
    assert 'runAnalysisCommand("analysis_reanalyze", { trackId, preferredProvider: null })' in js
    assert "const capabilityId = selectedCapability.capability_id;" in js
    assert "selectedLibrary.textContent = capability.display_name;" in js
    assert "selectedLibrary.textContent = capability.capability_id;" not in js


def test_renderer_prevents_duplicate_actions_and_supports_bounded_cancel() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    assert 'id="cancel-import"' in html
    assert 'id="cancel-analysis"' in html
    assert 'if (importBusy || typeof invoke !== "function")' in js
    assert "importButton.disabled = importBusy || selectedCapability === null;" in js
    assert "cancelButton.disabled = !importBusy || activeImportJobId === null || importCancelRequested;" in js
    assert "analyzeSelectedButton.disabled = analysisBusy || selectedAnalysisTrackIds.size === 0;" in js
    assert "cancelAnalysisButton.disabled = !analysisBusy || activeAnalysisJobId === null || analysisCancelRequested;" in js
    assert 'importSection.setAttribute("aria-busy", importBusy ? "true" : "false");' in js
    assert 'analysisSection.setAttribute("aria-busy", analysisBusy ? "true" : "false");' in js
    assert "const POLL_INTERVAL_MS = 250;" in js
    assert "await delay(POLL_INTERVAL_MS);" in js
    assert "importCountsDoNotRegress(snapshot.counts, next.counts)" in js
    assert "analysisCountsDoNotRegress(snapshot.counts, next.counts)" in js


def test_renderer_validates_bounded_import_and_analysis_models() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    for required_id in (
        'id="import-progress"',
        'id="library-results"',
        'id="library-rows"',
        'id="analysis"',
        'id="analyze-selected"',
        'id="analysis-progress"',
        'id="inspector-filter"',
        'id="inspector-table"',
        'id="inspector-rows"',
        'id="analysis-detail"',
        'id="correction-form"',
        'id="reanalyze-track"',
    ):
        assert required_id in html

    assert "/^lij_[0-9a-f]{32}$/" in js
    assert "/^daj_[0-9a-f]{32}$/" in js
    assert "IMPORT_JOB_STATES.has(value.state)" in js
    assert "ANALYSIS_JOB_STATES.has(value.state)" in js
    assert "validImportCounts(value.counts)" in js
    assert "validAnalysisCounts(value.counts)" in js
    assert "exactKeys(value" in js
    assert "validInspectorItem" in js
    assert "validInspectorList" in js
    assert "INSPECTOR_FILTERS" in js
    assert "INSPECTOR_SOURCES" in js
    assert "pathShapedText" in js
    assert "validTrackId" in js
    assert "renderLibraryTracks(result.tracks);" in js
    assert "renderInspectorList(result);" in js
    assert "renderInspectorDetail(item);" in js
    assert "values.bpm = bpm;" in js
    assert "values.energy = energy;" in js
    assert "track.title || track.file_name" in js
    assert "displayFormat(track.file_name)" in js
    assert "issue.file_name" in js
    assert ".path" not in js
    assert "absolute_path" not in js
    assert "process_id" not in js
    assert "nonce_sha256" not in js
    assert "aj_" not in js


def test_renderer_has_accessible_import_analysis_and_inspector_regions() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert html.count('role="status"') == 2
    assert html.count('aria-live="polite"') == 2
    assert html.count('aria-busy="false"') == 2
    assert "<caption>Imported library tracks</caption>" in html
    assert "<caption>Persisted analysis evidence</caption>" in html
    assert html.count('scope="col"') == 15
    assert 'aria-labelledby="import-progress-heading"' in html
    assert 'aria-labelledby="analysis-progress-heading"' in html
    assert 'aria-labelledby="analysis-inspector-heading"' in html


def test_renderer_has_no_network_shell_filesystem_or_sidecar_authority() -> None:
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
        "/v1/analysis/",
        "X-APPLAYLIST-Sidecar-Secret",
        "X-APPLAYLIST-Readiness-Nonce",
        "127.0.0.1",
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
        "allow-analysis-start",
        "allow-analysis-status",
        "allow-analysis-cancel",
        "allow-analysis-inspector-list",
        "allow-analysis-inspector-get",
        "allow-analysis-correct",
        "allow-analysis-reanalyze",
    ]


def test_tauri_build_handler_and_capability_command_surfaces_match_exactly() -> None:
    build_rs = BUILD_RS.read_text(encoding="utf-8")
    lib_rs = LIB_RS.read_text(encoding="utf-8")
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))

    build_commands = set(re.findall(r'"((?:library|analysis)_[a-z_]+)"', build_rs))
    handler_commands = set(
        re.findall(
            r"(?:library_capability|import_job|analysis_job)::((?:library|analysis)_[a-z_]+)",
            lib_rs,
        )
    )
    expected_permissions = {
        f"allow-{command.replace('_', '-')}" for command in EXPECTED_COMMANDS
    }

    assert build_commands == EXPECTED_COMMANDS
    assert handler_commands == EXPECTED_COMMANDS
    assert set(capability["permissions"]) == expected_permissions
    assert "library_import_root" not in build_commands
    assert "library_import_root" not in handler_commands


def test_analysis_rust_boundary_keeps_python_job_and_sidecar_internals_out_of_renderer() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    job_rs = ANALYSIS_JOB_RS.read_text(encoding="utf-8")
    bridge_rs = ANALYSIS_BRIDGE_RS.read_text(encoding="utf-8")

    assert 'const ANALYSIS_JOB_PREFIX: &str = "daj_";' in job_rs
    assert 'strip_prefix("aj_")' in bridge_rs
    assert "SidecarAnalysisSnapshotDto" in bridge_rs
    assert "#[serde(deny_unknown_fields)]" in bridge_rs
    assert "stderr(Stdio::null())" in bridge_rs
    assert 'ready.host != "127.0.0.1"' in bridge_rs
    assert '"/v1/analysis/start"' in bridge_rs
    assert '"/v1/analysis/status"' in bridge_rs
    assert '"/v1/analysis/cancel"' in bridge_rs
    assert '"/v1/analysis/inspector/list"' in bridge_rs
    assert '"/v1/analysis/inspector/get"' in bridge_rs
    assert '"/v1/analysis/correct"' in bridge_rs
    assert '"/v1/analysis/reanalyze"' in bridge_rs
    assert "aj_" not in js
    assert "/v1/analysis/" not in js
