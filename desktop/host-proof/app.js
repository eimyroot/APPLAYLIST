(() => {
  "use strict";

  const POLL_INTERVAL_MS = 250;
  const IMPORT_JOB_STATES = new Set([
    "pending",
    "running",
    "cancelling",
    "succeeded",
    "cancelled",
    "failed",
  ]);
  const IMPORT_JOB_PHASES = new Set([
    "starting",
    "scanning",
    "importing",
    "persisting",
    "finalizing",
  ]);
  const IMPORT_TERMINAL_STATES = new Set(["succeeded", "cancelled", "failed"]);
  const ANALYSIS_JOB_STATES = new Set(["running", "cancelling", "done", "failed", "cancelled"]);
  const ANALYSIS_TERMINAL_STATES = new Set(["done", "failed", "cancelled"]);
  const INSPECTOR_FILTERS = new Set(["all", "uncertain", "failed", "corrected"]);
  const INSPECTOR_STATUSES = new Set(["succeeded", "failed"]);
  const INSPECTOR_SOURCES = new Set(["provider", "manual-correction"]);

  const chooseButton = document.getElementById("choose-library");
  const importButton = document.getElementById("import-library");
  const cancelButton = document.getElementById("cancel-import");
  const importSection = document.getElementById("library-import");
  const selectedLibrary = document.getElementById("selected-library");
  const status = document.getElementById("status");
  const progressPanel = document.getElementById("import-progress");
  const progressPhase = document.getElementById("progress-phase");
  const progressDiscovered = document.getElementById("progress-discovered");
  const progressAccepted = document.getElementById("progress-accepted");
  const progressImported = document.getElementById("progress-imported");
  const progressPersisted = document.getElementById("progress-persisted");
  const summary = document.getElementById("import-summary");
  const summaryLibrary = document.getElementById("summary-library");
  const summaryDiscovered = document.getElementById("summary-discovered");
  const summaryAccepted = document.getElementById("summary-accepted");
  const summaryImported = document.getElementById("summary-imported");
  const summaryPersisted = document.getElementById("summary-persisted");
  const summaryIssues = document.getElementById("summary-issues");
  const libraryResults = document.getElementById("library-results");
  const libraryTable = document.getElementById("library-table");
  const libraryRows = document.getElementById("library-rows");
  const libraryEmpty = document.getElementById("library-empty");
  const issuesPanel = document.getElementById("import-issues");
  const issueList = document.getElementById("issue-list");

  const analysisSection = document.getElementById("analysis");
  const analyzeSelectedButton = document.getElementById("analyze-selected");
  const cancelAnalysisButton = document.getElementById("cancel-analysis");
  const refreshInspectorButton = document.getElementById("refresh-inspector");
  const inspectorFilter = document.getElementById("inspector-filter");
  const analysisStatus = document.getElementById("analysis-status");
  const analysisProgress = document.getElementById("analysis-progress");
  const analysisProgressState = document.getElementById("analysis-progress-state");
  const analysisProgressSelected = document.getElementById("analysis-progress-selected");
  const analysisProgressCompleted = document.getElementById("analysis-progress-completed");
  const analysisProgressSucceeded = document.getElementById("analysis-progress-succeeded");
  const analysisProgressFailed = document.getElementById("analysis-progress-failed");
  const analysisProgressUncertain = document.getElementById("analysis-progress-uncertain");
  const inspectorEmpty = document.getElementById("inspector-empty");
  const inspectorTable = document.getElementById("inspector-table");
  const inspectorRows = document.getElementById("inspector-rows");
  const analysisDetail = document.getElementById("analysis-detail");
  const detailTrack = document.getElementById("detail-track");
  const detailProvider = document.getElementById("detail-provider");
  const detailBpmConfidence = document.getElementById("detail-bpm-confidence");
  const detailKeyConfidence = document.getElementById("detail-key-confidence");
  const detailEvidence = document.getElementById("detail-evidence");
  const detailError = document.getElementById("detail-error");
  const detailWarnings = document.getElementById("detail-warnings");
  const correctionForm = document.getElementById("correction-form");
  const correctionBpm = document.getElementById("correction-bpm");
  const correctionKeyTonic = document.getElementById("correction-key-tonic");
  const correctionKeyScale = document.getElementById("correction-key-scale");
  const correctionCamelot = document.getElementById("correction-camelot");
  const correctionEnergy = document.getElementById("correction-energy");
  const correctionReason = document.getElementById("correction-reason");
  const applyCorrectionButton = document.getElementById("apply-correction");
  const reanalyzeTrackButton = document.getElementById("reanalyze-track");

  const invoke = window.__TAURI__?.core?.invoke;
  let selectedCapability = null;
  let activeImportJobId = null;
  let importBusy = false;
  let importCancelRequested = false;
  let importedTracks = new Map();
  let selectedAnalysisTrackIds = new Set();
  let activeAnalysisJobId = null;
  let analysisBusy = false;
  let analysisCancelRequested = false;
  let activeInspectorTrackId = null;

  function exactKeys(value, expected) {
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return false;
    }
    const keys = Object.keys(value).sort();
    const required = [...expected].sort();
    return keys.length === required.length && keys.every((key, index) => key === required[index]);
  }

  function nullableText(value) {
    return value === null || typeof value === "string";
  }

  function boundedText(value, maximum) {
    return typeof value === "string" && value.length > 0 && value.length <= maximum && !/[\u0000-\u001f]/.test(value);
  }

  function pathShapedText(value) {
    return (
      typeof value === "string" &&
      (value.startsWith("/") || value.startsWith("\\\\") || /^[A-Za-z]:[\\/]/.test(value))
    );
  }

  function validTrackId(value) {
    return boundedText(value, 256) && !value.includes("/") && !value.includes("\\") && value.trim() === value;
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function setAnalysisStatus(message) {
    analysisStatus.textContent = message;
  }

  function updateImportControls() {
    chooseButton.disabled = importBusy;
    importButton.disabled = importBusy || selectedCapability === null;
    cancelButton.disabled = !importBusy || activeImportJobId === null || importCancelRequested;
    importSection.setAttribute("aria-busy", importBusy ? "true" : "false");
  }

  function setImportBusy(nextBusy) {
    importBusy = nextBusy;
    updateImportControls();
  }

  function updateAnalysisControls() {
    analyzeSelectedButton.disabled = analysisBusy || selectedAnalysisTrackIds.size === 0;
    cancelAnalysisButton.disabled = !analysisBusy || activeAnalysisJobId === null || analysisCancelRequested;
    refreshInspectorButton.disabled = analysisBusy;
    inspectorFilter.disabled = analysisBusy;
    reanalyzeTrackButton.disabled = analysisBusy || activeInspectorTrackId === null;
    applyCorrectionButton.disabled = analysisBusy || activeInspectorTrackId === null;
    analysisSection.setAttribute("aria-busy", analysisBusy ? "true" : "false");
  }

  function setAnalysisBusy(nextBusy) {
    analysisBusy = nextBusy;
    updateAnalysisControls();
  }

  function validCapability(value) {
    return (
      exactKeys(value, ["capability_id", "display_name"]) &&
      boundedText(value.capability_id, 128) &&
      boundedText(value.display_name, 128)
    );
  }

  function validImportCounts(value) {
    return (
      exactKeys(value, ["discovered_entries", "accepted", "imported", "persisted"]) &&
      Number.isInteger(value.discovered_entries) &&
      value.discovered_entries >= 0 &&
      Number.isInteger(value.accepted) &&
      value.accepted >= 0 &&
      Number.isInteger(value.imported) &&
      value.imported >= 0 &&
      Number.isInteger(value.persisted) &&
      value.persisted >= 0 &&
      value.persisted <= value.imported &&
      value.imported <= value.accepted &&
      value.accepted <= value.discovered_entries
    );
  }

  function validTrack(value) {
    return (
      exactKeys(value, [
        "track_id",
        "file_name",
        "title",
        "artist",
        "album",
        "genre",
        "duration_seconds",
        "metadata_origin",
        "relinked",
      ]) &&
      validTrackId(value.track_id) &&
      boundedText(value.file_name, 512) &&
      !value.file_name.includes("/") &&
      !value.file_name.includes("\\") &&
      nullableText(value.title) &&
      nullableText(value.artist) &&
      nullableText(value.album) &&
      nullableText(value.genre) &&
      (value.duration_seconds === null ||
        (typeof value.duration_seconds === "number" && Number.isFinite(value.duration_seconds) && value.duration_seconds >= 0)) &&
      boundedText(value.metadata_origin, 128) &&
      typeof value.relinked === "boolean"
    );
  }

  function validIssue(value) {
    return (
      exactKeys(value, ["stage", "code", "file_name"]) &&
      boundedText(value.stage, 128) &&
      boundedText(value.code, 128) &&
      (value.file_name === null ||
        (boundedText(value.file_name, 512) && !value.file_name.includes("/") && !value.file_name.includes("\\")))
    );
  }

  function validImportResult(value) {
    return (
      exactKeys(value, [
        "folder_name",
        "tracks",
        "issues",
        "counts",
        "cancelled",
        "entry_limit_reached",
        "file_limit_reached",
        "complete",
      ]) &&
      boundedText(value.folder_name, 512) &&
      !pathShapedText(value.folder_name) &&
      validImportCounts(value.counts) &&
      Array.isArray(value.tracks) &&
      value.tracks.every(validTrack) &&
      Array.isArray(value.issues) &&
      value.issues.every(validIssue) &&
      typeof value.complete === "boolean" &&
      typeof value.cancelled === "boolean" &&
      typeof value.entry_limit_reached === "boolean" &&
      typeof value.file_limit_reached === "boolean"
    );
  }

  function validImportJobSnapshot(value) {
    if (
      !exactKeys(value, ["import_job_id", "state", "phase", "counts", "terminal", "result", "error_code"]) ||
      typeof value.import_job_id !== "string" ||
      !/^lij_[0-9a-f]{32}$/.test(value.import_job_id) ||
      !IMPORT_JOB_STATES.has(value.state) ||
      !IMPORT_JOB_PHASES.has(value.phase) ||
      !validImportCounts(value.counts) ||
      typeof value.terminal !== "boolean" ||
      !nullableText(value.error_code)
    ) {
      return false;
    }
    if (value.terminal !== IMPORT_TERMINAL_STATES.has(value.state)) {
      return false;
    }
    if (!value.terminal) {
      return value.result === null;
    }
    if (value.state === "failed") {
      return value.result === null;
    }
    return validImportResult(value.result);
  }

  function importCountsDoNotRegress(previous, next) {
    return (
      next.discovered_entries >= previous.discovered_entries &&
      next.accepted >= previous.accepted &&
      next.imported >= previous.imported &&
      next.persisted >= previous.persisted
    );
  }

  function validAnalysisCounts(value) {
    return (
      exactKeys(value, ["selected", "completed", "succeeded", "failed", "uncertain"]) &&
      Number.isInteger(value.selected) &&
      value.selected > 0 &&
      value.selected <= 10000 &&
      Number.isInteger(value.completed) &&
      value.completed >= 0 &&
      Number.isInteger(value.succeeded) &&
      value.succeeded >= 0 &&
      Number.isInteger(value.failed) &&
      value.failed >= 0 &&
      Number.isInteger(value.uncertain) &&
      value.uncertain >= 0 &&
      value.completed === value.succeeded + value.failed &&
      value.completed <= value.selected &&
      value.uncertain <= value.succeeded
    );
  }

  function validAnalysisJobSnapshot(value) {
    if (
      !exactKeys(value, ["analysis_job_id", "state", "counts", "terminal", "error_code"]) ||
      typeof value.analysis_job_id !== "string" ||
      !/^daj_[0-9a-f]{32}$/.test(value.analysis_job_id) ||
      !ANALYSIS_JOB_STATES.has(value.state) ||
      !validAnalysisCounts(value.counts) ||
      typeof value.terminal !== "boolean" ||
      !nullableText(value.error_code)
    ) {
      return false;
    }
    if (value.terminal !== ANALYSIS_TERMINAL_STATES.has(value.state)) {
      return false;
    }
    return value.state !== "done" || value.counts.completed === value.counts.selected;
  }

  function analysisCountsDoNotRegress(previous, next) {
    return (
      next.selected === previous.selected &&
      next.completed >= previous.completed &&
      next.succeeded >= previous.succeeded &&
      next.failed >= previous.failed &&
      next.uncertain >= previous.uncertain
    );
  }

  function validOptionalNumber(value, minimum, maximum) {
    return value === null || (typeof value === "number" && Number.isFinite(value) && value >= minimum && value <= maximum);
  }

  function validOptionalBoundedText(value, maximum, rejectPathShape = false) {
    return (
      value === null ||
      (boundedText(value, maximum) && (!rejectPathShape || !pathShapedText(value)))
    );
  }

  function validInspectorItem(value) {
    if (
      !exactKeys(value, [
        "track_id",
        "title",
        "artist",
        "status",
        "bpm",
        "bpm_confidence",
        "key_tonic",
        "key_scale",
        "camelot",
        "key_confidence",
        "energy",
        "duration_seconds",
        "provider",
        "provider_version",
        "analysis_version",
        "algorithm_version",
        "warnings",
        "source",
        "uncertain",
        "corrected",
        "attempt_evidence_id",
        "effective_evidence_id",
        "correction_id",
        "correction_reason",
        "error_code",
        "error_detail",
      ]) ||
      !validTrackId(value.track_id) ||
      !boundedText(value.title, 512) ||
      pathShapedText(value.title) ||
      !validOptionalBoundedText(value.artist, 512, true) ||
      !INSPECTOR_STATUSES.has(value.status) ||
      !validOptionalNumber(value.bpm, 0, 400) ||
      !validOptionalNumber(value.bpm_confidence, 0, 1) ||
      !validOptionalBoundedText(value.key_tonic, 32) ||
      !validOptionalBoundedText(value.key_scale, 32) ||
      !validOptionalBoundedText(value.camelot, 32) ||
      !validOptionalNumber(value.key_confidence, 0, 1) ||
      !validOptionalNumber(value.energy, 0, 1) ||
      (value.duration_seconds !== null &&
        (typeof value.duration_seconds !== "number" || !Number.isFinite(value.duration_seconds) || value.duration_seconds < 0)) ||
      !boundedText(value.provider, 128) ||
      !validOptionalBoundedText(value.provider_version, 128) ||
      !boundedText(value.analysis_version, 128) ||
      !validOptionalBoundedText(value.algorithm_version, 128) ||
      !Array.isArray(value.warnings) ||
      !value.warnings.every((warning) => boundedText(warning, 512) && !pathShapedText(warning)) ||
      !INSPECTOR_SOURCES.has(value.source) ||
      typeof value.uncertain !== "boolean" ||
      typeof value.corrected !== "boolean" ||
      !boundedText(value.attempt_evidence_id, 256) ||
      !validOptionalBoundedText(value.effective_evidence_id, 256) ||
      !validOptionalBoundedText(value.correction_id, 256) ||
      !validOptionalBoundedText(value.correction_reason, 512, true) ||
      !validOptionalBoundedText(value.error_code, 128) ||
      !validOptionalBoundedText(value.error_detail, 512, true)
    ) {
      return false;
    }
    if (value.corrected !== (value.source === "manual-correction")) {
      return false;
    }
    if (value.status === "failed" && value.error_code === null) {
      return false;
    }
    return true;
  }

  function validInspectorList(value) {
    return (
      exactKeys(value, ["filter", "items"]) &&
      INSPECTOR_FILTERS.has(value.filter) &&
      Array.isArray(value.items) &&
      value.items.every(validInspectorItem)
    );
  }

  function errorMessage(error) {
    if (
      error !== null &&
      typeof error === "object" &&
      typeof error.message === "string" &&
      error.message.length > 0
    ) {
      return error.message;
    }
    return "The desktop host could not complete the request.";
  }

  function delay(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function displayFormat(fileName) {
    const dot = fileName.lastIndexOf(".");
    if (dot <= 0 || dot === fileName.length - 1) {
      return "Unknown";
    }
    return fileName.slice(dot + 1).toUpperCase();
  }

  function displayDuration(durationSeconds) {
    if (durationSeconds === null) {
      return "—";
    }
    const totalSeconds = Math.max(0, Math.round(durationSeconds));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${minutes}:${seconds}`;
  }

  function displayNumber(value, digits = 2) {
    return value === null ? "—" : Number(value).toFixed(digits);
  }

  function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.appendChild(cell);
  }

  function renderImportProgress(snapshot) {
    progressPhase.textContent = snapshot.phase;
    progressDiscovered.textContent = String(snapshot.counts.discovered_entries);
    progressAccepted.textContent = String(snapshot.counts.accepted);
    progressImported.textContent = String(snapshot.counts.imported);
    progressPersisted.textContent = String(snapshot.counts.persisted);
    progressPanel.hidden = false;
  }

  function renderImportSummary(result) {
    summaryLibrary.textContent = result.folder_name;
    summaryDiscovered.textContent = String(result.counts.discovered_entries);
    summaryAccepted.textContent = String(result.counts.accepted);
    summaryImported.textContent = String(result.counts.imported);
    summaryPersisted.textContent = String(result.counts.persisted);
    summaryIssues.textContent = String(result.issues.length);
    summary.hidden = false;
  }

  function renderLibraryTracks(tracks) {
    importedTracks = new Map(tracks.map((track) => [track.track_id, track]));
    selectedAnalysisTrackIds = new Set();
    libraryRows.replaceChildren();
    libraryResults.hidden = false;
    analysisSection.hidden = tracks.length === 0;
    activeInspectorTrackId = null;
    analysisDetail.hidden = true;

    if (tracks.length === 0) {
      libraryTable.hidden = true;
      libraryEmpty.hidden = false;
      updateAnalysisControls();
      return;
    }

    libraryEmpty.hidden = true;
    libraryTable.hidden = false;

    for (const track of tracks) {
      const row = document.createElement("tr");
      const selectCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.setAttribute("aria-label", `Analyze ${track.title || track.file_name}`);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          selectedAnalysisTrackIds.add(track.track_id);
        } else {
          selectedAnalysisTrackIds.delete(track.track_id);
        }
        updateAnalysisControls();
      });
      selectCell.appendChild(checkbox);
      row.appendChild(selectCell);
      appendCell(row, track.title || track.file_name);
      appendCell(row, track.artist || "Unknown artist");
      appendCell(row, displayFormat(track.file_name));
      appendCell(row, displayDuration(track.duration_seconds));
      appendCell(row, track.relinked ? "Relinked" : "Imported");
      appendCell(row, track.metadata_origin);
      libraryRows.appendChild(row);
    }
    setAnalysisStatus("Select imported tracks to analyze.");
    updateAnalysisControls();
  }

  function renderIssues(issues) {
    issueList.replaceChildren();
    if (issues.length === 0) {
      issuesPanel.hidden = true;
      return;
    }
    for (const issue of issues) {
      const item = document.createElement("li");
      const file = issue.file_name ? ` — ${issue.file_name}` : "";
      item.textContent = `${issue.stage}: ${issue.code}${file}`;
      issueList.appendChild(item);
    }
    issuesPanel.hidden = false;
  }

  function renderAnalysisProgress(snapshot) {
    analysisProgressState.textContent = snapshot.state;
    analysisProgressSelected.textContent = String(snapshot.counts.selected);
    analysisProgressCompleted.textContent = String(snapshot.counts.completed);
    analysisProgressSucceeded.textContent = String(snapshot.counts.succeeded);
    analysisProgressFailed.textContent = String(snapshot.counts.failed);
    analysisProgressUncertain.textContent = String(snapshot.counts.uncertain);
    analysisProgress.hidden = false;
  }

  function renderInspectorList(result) {
    inspectorRows.replaceChildren();
    if (result.items.length === 0) {
      inspectorTable.hidden = true;
      inspectorEmpty.hidden = false;
      return;
    }
    inspectorEmpty.hidden = true;
    inspectorTable.hidden = false;
    for (const item of result.items) {
      const row = document.createElement("tr");
      appendCell(row, item.title);
      appendCell(row, item.artist || "Unknown artist");
      appendCell(row, item.status);
      appendCell(row, displayNumber(item.bpm));
      appendCell(row, item.camelot || [item.key_tonic, item.key_scale].filter(Boolean).join(" ") || "—");
      appendCell(row, displayNumber(item.energy));
      appendCell(row, item.source);
      const actionCell = document.createElement("td");
      const inspectButton = document.createElement("button");
      inspectButton.type = "button";
      inspectButton.textContent = "Inspect";
      inspectButton.addEventListener("click", () => inspectTrack(item.track_id));
      actionCell.appendChild(inspectButton);
      row.appendChild(actionCell);
      inspectorRows.appendChild(row);
    }
  }

  function renderInspectorDetail(item) {
    activeInspectorTrackId = item.track_id;
    detailTrack.textContent = `${item.title}${item.artist ? ` — ${item.artist}` : ""}`;
    detailProvider.textContent = `${item.provider}${item.provider_version ? ` ${item.provider_version}` : ""}`;
    detailBpmConfidence.textContent = displayNumber(item.bpm_confidence);
    detailKeyConfidence.textContent = displayNumber(item.key_confidence);
    detailEvidence.textContent = item.effective_evidence_id || item.attempt_evidence_id;
    detailError.textContent = item.error_code ? `${item.error_code}${item.error_detail ? ` — ${item.error_detail}` : ""}` : "—";
    detailWarnings.replaceChildren();
    for (const warning of item.warnings) {
      const entry = document.createElement("li");
      entry.textContent = warning;
      detailWarnings.appendChild(entry);
    }
    if (item.warnings.length === 0) {
      const entry = document.createElement("li");
      entry.textContent = "None";
      detailWarnings.appendChild(entry);
    }
    correctionBpm.value = item.bpm === null ? "" : String(item.bpm);
    correctionKeyTonic.value = item.key_tonic || "";
    correctionKeyScale.value = item.key_scale || "";
    correctionCamelot.value = item.camelot || "";
    correctionEnergy.value = item.energy === null ? "" : String(item.energy);
    correctionReason.value = "";
    applyCorrectionButton.disabled = analysisBusy || item.effective_evidence_id === null;
    analysisDetail.hidden = false;
    updateAnalysisControls();
    if (item.effective_evidence_id === null) {
      applyCorrectionButton.disabled = true;
    }
  }

  function clearResults() {
    summary.hidden = true;
    libraryResults.hidden = true;
    libraryTable.hidden = true;
    libraryEmpty.hidden = true;
    issuesPanel.hidden = true;
    analysisSection.hidden = true;
    analysisDetail.hidden = true;
    inspectorTable.hidden = true;
    inspectorEmpty.hidden = false;
    libraryRows.replaceChildren();
    issueList.replaceChildren();
    inspectorRows.replaceChildren();
    importedTracks = new Map();
    selectedAnalysisTrackIds = new Set();
    activeInspectorTrackId = null;
  }

  function clearImportProgress() {
    progressPanel.hidden = true;
    progressPhase.textContent = "—";
    progressDiscovered.textContent = "0";
    progressAccepted.textContent = "0";
    progressImported.textContent = "0";
    progressPersisted.textContent = "0";
  }

  function clearAnalysisProgress() {
    analysisProgress.hidden = true;
    analysisProgressState.textContent = "—";
    analysisProgressSelected.textContent = "0";
    analysisProgressCompleted.textContent = "0";
    analysisProgressSucceeded.textContent = "0";
    analysisProgressFailed.textContent = "0";
    analysisProgressUncertain.textContent = "0";
  }

  async function chooseLibrary() {
    if (importBusy || typeof invoke !== "function") {
      return;
    }
    setImportBusy(true);
    setStatus("Choose a library folder.");
    try {
      const capability = await invoke("library_choose_root");
      if (capability === null) {
        setStatus("Selection cancelled.");
        return;
      }
      if (!validCapability(capability)) {
        throw new Error("The desktop host returned an invalid library selection.");
      }
      selectedCapability = capability;
      selectedLibrary.textContent = capability.display_name;
      clearResults();
      clearImportProgress();
      clearAnalysisProgress();
      setStatus("Library selected. Ready to import.");
    } catch (error) {
      setStatus(errorMessage(error));
    } finally {
      setImportBusy(false);
    }
  }

  async function pollImport(initialSnapshot) {
    let snapshot = initialSnapshot;
    renderImportProgress(snapshot);
    while (!snapshot.terminal) {
      await delay(POLL_INTERVAL_MS);
      const next = await invoke("library_import_status", {
        importJobId: snapshot.import_job_id,
      });
      if (!validImportJobSnapshot(next)) {
        throw new Error("The desktop host returned an invalid import status.");
      }
      if (
        next.import_job_id !== snapshot.import_job_id ||
        !importCountsDoNotRegress(snapshot.counts, next.counts)
      ) {
        throw new Error("The desktop host returned a regressive import status.");
      }
      snapshot = next;
      renderImportProgress(snapshot);
    }
    return snapshot;
  }

  async function importLibrary() {
    if (importBusy || typeof invoke !== "function" || selectedCapability === null) {
      return;
    }
    const capabilityId = selectedCapability.capability_id;
    setImportBusy(true);
    clearResults();
    clearImportProgress();
    clearAnalysisProgress();
    setStatus("Starting library import…");
    try {
      const initial = await invoke("library_import_start", { capabilityId });
      if (!validImportJobSnapshot(initial)) {
        throw new Error("The desktop host returned an invalid import job.");
      }
      activeImportJobId = initial.import_job_id;
      importCancelRequested = false;
      updateImportControls();
      const terminal = await pollImport(initial);
      if (terminal.state === "failed") {
        throw new Error("The desktop import failed safely.");
      }
      const result = terminal.result;
      if (!validImportResult(result)) {
        throw new Error("The desktop host returned an invalid import result.");
      }
      renderImportSummary(result);
      renderLibraryTracks(result.tracks);
      renderIssues(result.issues);
      if (terminal.state === "cancelled" || result.cancelled) {
        setStatus("Import cancelled. Partial results are shown.");
      } else if (result.complete) {
        setStatus(`Import complete. ${result.counts.persisted} tracks persisted.`);
      } else {
        setStatus("Import stopped before completion. Partial results are shown.");
      }
    } catch (error) {
      clearResults();
      setStatus(errorMessage(error));
    } finally {
      activeImportJobId = null;
      importCancelRequested = false;
      setImportBusy(false);
    }
  }

  async function cancelImport() {
    if (!importBusy || typeof invoke !== "function" || activeImportJobId === null || importCancelRequested) {
      return;
    }
    importCancelRequested = true;
    updateImportControls();
    setStatus("Cancelling library import…");
    try {
      const snapshot = await invoke("library_import_cancel", {
        importJobId: activeImportJobId,
      });
      if (!validImportJobSnapshot(snapshot) || snapshot.import_job_id !== activeImportJobId) {
        throw new Error("The desktop host returned an invalid cancellation state.");
      }
      renderImportProgress(snapshot);
      if (snapshot.terminal && snapshot.state !== "cancelled") {
        setStatus("Import had already completed before cancellation.");
      }
    } catch (error) {
      importCancelRequested = false;
      updateImportControls();
      setStatus(errorMessage(error));
    }
  }

  async function pollAnalysis(initialSnapshot) {
    let snapshot = initialSnapshot;
    renderAnalysisProgress(snapshot);
    while (!snapshot.terminal) {
      await delay(POLL_INTERVAL_MS);
      const next = await invoke("analysis_status", {
        analysisJobId: snapshot.analysis_job_id,
      });
      if (!validAnalysisJobSnapshot(next)) {
        throw new Error("The desktop host returned an invalid analysis status.");
      }
      if (
        next.analysis_job_id !== snapshot.analysis_job_id ||
        !analysisCountsDoNotRegress(snapshot.counts, next.counts)
      ) {
        throw new Error("The desktop host returned a regressive analysis status.");
      }
      snapshot = next;
      renderAnalysisProgress(snapshot);
    }
    return snapshot;
  }

  async function runAnalysisCommand(command, argumentsPayload) {
    if (analysisBusy || typeof invoke !== "function") {
      return;
    }
    setAnalysisBusy(true);
    analysisCancelRequested = false;
    clearAnalysisProgress();
    setAnalysisStatus("Starting analysis…");
    try {
      const initial = await invoke(command, argumentsPayload);
      if (!validAnalysisJobSnapshot(initial)) {
        throw new Error("The desktop host returned an invalid analysis job.");
      }
      activeAnalysisJobId = initial.analysis_job_id;
      updateAnalysisControls();
      const terminal = await pollAnalysis(initial);
      if (terminal.state === "failed") {
        setAnalysisStatus("Analysis failed safely. Inspect persisted evidence for track-level outcomes.");
      } else if (terminal.state === "cancelled") {
        setAnalysisStatus("Analysis cancelled. Completed track evidence remains available.");
      } else {
        setAnalysisStatus(`Analysis complete. ${terminal.counts.succeeded} succeeded, ${terminal.counts.failed} failed, ${terminal.counts.uncertain} uncertain.`);
      }
    } catch (error) {
      setAnalysisStatus(errorMessage(error));
    } finally {
      activeAnalysisJobId = null;
      analysisCancelRequested = false;
      setAnalysisBusy(false);
      await refreshInspector();
    }
  }

  async function analyzeSelected() {
    const trackIds = [...selectedAnalysisTrackIds];
    if (trackIds.length === 0) {
      setAnalysisStatus("Select at least one imported track.");
      return;
    }
    await runAnalysisCommand("analysis_start", { trackIds, preferredProvider: null });
  }

  async function cancelAnalysis() {
    if (!analysisBusy || typeof invoke !== "function" || activeAnalysisJobId === null || analysisCancelRequested) {
      return;
    }
    analysisCancelRequested = true;
    updateAnalysisControls();
    setAnalysisStatus("Cancelling analysis…");
    try {
      const snapshot = await invoke("analysis_cancel", {
        analysisJobId: activeAnalysisJobId,
      });
      if (!validAnalysisJobSnapshot(snapshot) || snapshot.analysis_job_id !== activeAnalysisJobId) {
        throw new Error("The desktop host returned an invalid analysis cancellation state.");
      }
      renderAnalysisProgress(snapshot);
    } catch (error) {
      analysisCancelRequested = false;
      updateAnalysisControls();
      setAnalysisStatus(errorMessage(error));
    }
  }

  async function refreshInspector() {
    if (typeof invoke !== "function" || analysisSection.hidden) {
      return;
    }
    const filter = inspectorFilter.value;
    if (!INSPECTOR_FILTERS.has(filter)) {
      setAnalysisStatus("The inspector filter is invalid.");
      return;
    }
    try {
      const result = await invoke("analysis_inspector_list", { filter });
      if (!validInspectorList(result) || result.filter !== filter) {
        throw new Error("The desktop host returned an invalid inspector list.");
      }
      renderInspectorList(result);
    } catch (error) {
      inspectorRows.replaceChildren();
      inspectorTable.hidden = true;
      inspectorEmpty.hidden = false;
      setAnalysisStatus(errorMessage(error));
    }
  }

  async function inspectTrack(trackId) {
    if (typeof invoke !== "function" || !validTrackId(trackId)) {
      return;
    }
    try {
      const item = await invoke("analysis_inspector_get", { trackId });
      if (!validInspectorItem(item) || item.track_id !== trackId) {
        throw new Error("The desktop host returned an invalid inspector item.");
      }
      renderInspectorDetail(item);
    } catch (error) {
      analysisDetail.hidden = true;
      activeInspectorTrackId = null;
      updateAnalysisControls();
      setAnalysisStatus(errorMessage(error));
    }
  }

  function correctionValues() {
    const values = {};
    if (correctionBpm.value !== "") {
      const bpm = Number(correctionBpm.value);
      if (!Number.isFinite(bpm) || bpm < 20 || bpm > 300) {
        throw new Error("Corrected BPM must be between 20 and 300.");
      }
      values.bpm = bpm;
    }
    if (correctionKeyTonic.value.trim() !== "") {
      values.key_tonic = correctionKeyTonic.value.trim();
    }
    if (correctionKeyScale.value.trim() !== "") {
      values.key_scale = correctionKeyScale.value.trim();
    }
    if (correctionCamelot.value.trim() !== "") {
      values.camelot = correctionCamelot.value.trim();
    }
    if (correctionEnergy.value !== "") {
      const energy = Number(correctionEnergy.value);
      if (!Number.isFinite(energy) || energy < 0 || energy > 1) {
        throw new Error("Corrected energy must be between 0 and 1.");
      }
      values.energy = energy;
    }
    if (Object.keys(values).length === 0) {
      throw new Error("Enter at least one correction value.");
    }
    return values;
  }

  async function applyCorrection(event) {
    event.preventDefault();
    if (analysisBusy || typeof invoke !== "function" || activeInspectorTrackId === null) {
      return;
    }
    try {
      const values = correctionValues();
      const reason = correctionReason.value.trim() || null;
      const item = await invoke("analysis_correct", {
        trackId: activeInspectorTrackId,
        values,
        reason,
      });
      if (!validInspectorItem(item) || item.track_id !== activeInspectorTrackId || !item.corrected) {
        throw new Error("The desktop host returned an invalid corrected analysis item.");
      }
      renderInspectorDetail(item);
      setAnalysisStatus("Manual correction saved as append-only evidence overlay.");
      await refreshInspector();
    } catch (error) {
      setAnalysisStatus(errorMessage(error));
    }
  }

  async function reanalyzeTrack() {
    if (activeInspectorTrackId === null || !validTrackId(activeInspectorTrackId)) {
      return;
    }
    const trackId = activeInspectorTrackId;
    await runAnalysisCommand("analysis_reanalyze", { trackId, preferredProvider: null });
    await inspectTrack(trackId);
  }

  if (typeof invoke !== "function") {
    chooseButton.disabled = true;
    importButton.disabled = true;
    cancelButton.disabled = true;
    analyzeSelectedButton.disabled = true;
    cancelAnalysisButton.disabled = true;
    refreshInspectorButton.disabled = true;
    reanalyzeTrackButton.disabled = true;
    applyCorrectionButton.disabled = true;
    setStatus("Desktop bridge unavailable.");
    setAnalysisStatus("Desktop bridge unavailable.");
    return;
  }

  chooseButton.addEventListener("click", chooseLibrary);
  importButton.addEventListener("click", importLibrary);
  cancelButton.addEventListener("click", cancelImport);
  analyzeSelectedButton.addEventListener("click", analyzeSelected);
  cancelAnalysisButton.addEventListener("click", cancelAnalysis);
  refreshInspectorButton.addEventListener("click", refreshInspector);
  inspectorFilter.addEventListener("change", refreshInspector);
  correctionForm.addEventListener("submit", applyCorrection);
  reanalyzeTrackButton.addEventListener("click", reanalyzeTrack);
  setImportBusy(false);
  setAnalysisBusy(false);
})();