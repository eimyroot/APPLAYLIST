(() => {
  "use strict";

  const POLL_INTERVAL_MS = 250;
  const JOB_STATES = new Set([
    "pending",
    "running",
    "cancelling",
    "succeeded",
    "cancelled",
    "failed",
  ]);
  const JOB_PHASES = new Set([
    "starting",
    "scanning",
    "importing",
    "persisting",
    "finalizing",
  ]);
  const TERMINAL_STATES = new Set(["succeeded", "cancelled", "failed"]);

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

  const invoke = window.__TAURI__?.core?.invoke;
  let selectedCapability = null;
  let activeJobId = null;
  let busy = false;
  let cancelRequested = false;

  function setStatus(message) {
    status.textContent = message;
  }

  function updateControls() {
    chooseButton.disabled = busy;
    importButton.disabled = busy || selectedCapability === null;
    cancelButton.disabled = !busy || activeJobId === null || cancelRequested;
    importSection.setAttribute("aria-busy", busy ? "true" : "false");
  }

  function setBusy(nextBusy) {
    busy = nextBusy;
    updateControls();
  }

  function validCapability(value) {
    return (
      value !== null &&
      typeof value === "object" &&
      typeof value.capability_id === "string" &&
      value.capability_id.length > 0 &&
      typeof value.display_name === "string" &&
      value.display_name.length > 0
    );
  }

  function nullableText(value) {
    return value === null || typeof value === "string";
  }

  function validCounts(value) {
    return (
      value !== null &&
      typeof value === "object" &&
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
      value !== null &&
      typeof value === "object" &&
      typeof value.track_id === "string" &&
      value.track_id.length > 0 &&
      typeof value.file_name === "string" &&
      value.file_name.length > 0 &&
      nullableText(value.title) &&
      nullableText(value.artist) &&
      nullableText(value.album) &&
      nullableText(value.genre) &&
      (value.duration_seconds === null ||
        (typeof value.duration_seconds === "number" &&
          Number.isFinite(value.duration_seconds) &&
          value.duration_seconds >= 0)) &&
      typeof value.metadata_origin === "string" &&
      value.metadata_origin.length > 0 &&
      typeof value.relinked === "boolean"
    );
  }

  function validIssue(value) {
    return (
      value !== null &&
      typeof value === "object" &&
      typeof value.stage === "string" &&
      value.stage.length > 0 &&
      typeof value.code === "string" &&
      value.code.length > 0 &&
      (value.file_name === null || typeof value.file_name === "string")
    );
  }

  function validImportResult(value) {
    return (
      value !== null &&
      typeof value === "object" &&
      typeof value.folder_name === "string" &&
      validCounts(value.counts) &&
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

  function validJobSnapshot(value) {
    if (
      value === null ||
      typeof value !== "object" ||
      typeof value.import_job_id !== "string" ||
      !/^lij_[0-9a-f]{32}$/.test(value.import_job_id) ||
      !JOB_STATES.has(value.state) ||
      !JOB_PHASES.has(value.phase) ||
      !validCounts(value.counts) ||
      typeof value.terminal !== "boolean" ||
      !nullableText(value.error_code)
    ) {
      return false;
    }

    if (value.terminal !== TERMINAL_STATES.has(value.state)) {
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

  function countsDoNotRegress(previous, next) {
    return (
      next.discovered_entries >= previous.discovered_entries &&
      next.accepted >= previous.accepted &&
      next.imported >= previous.imported &&
      next.persisted >= previous.persisted
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

  function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.appendChild(cell);
  }

  function renderProgress(snapshot) {
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
    libraryRows.replaceChildren();
    libraryResults.hidden = false;

    if (tracks.length === 0) {
      libraryTable.hidden = true;
      libraryEmpty.hidden = false;
      return;
    }

    libraryEmpty.hidden = true;
    libraryTable.hidden = false;

    for (const track of tracks) {
      const row = document.createElement("tr");
      appendCell(row, track.title || track.file_name);
      appendCell(row, track.artist || "Unknown artist");
      appendCell(row, displayFormat(track.file_name));
      appendCell(row, displayDuration(track.duration_seconds));
      appendCell(row, track.relinked ? "Relinked" : "Imported");
      appendCell(row, track.metadata_origin);
      libraryRows.appendChild(row);
    }
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

  function clearResults() {
    summary.hidden = true;
    libraryResults.hidden = true;
    libraryTable.hidden = true;
    libraryEmpty.hidden = true;
    issuesPanel.hidden = true;
    libraryRows.replaceChildren();
    issueList.replaceChildren();
  }

  function clearProgress() {
    progressPanel.hidden = true;
    progressPhase.textContent = "—";
    progressDiscovered.textContent = "0";
    progressAccepted.textContent = "0";
    progressImported.textContent = "0";
    progressPersisted.textContent = "0";
  }

  async function chooseLibrary() {
    if (busy || typeof invoke !== "function") {
      return;
    }

    setBusy(true);
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
      clearProgress();
      setStatus("Library selected. Ready to import.");
    } catch (error) {
      setStatus(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function pollImport(initialSnapshot) {
    let snapshot = initialSnapshot;
    renderProgress(snapshot);

    while (!snapshot.terminal) {
      await delay(POLL_INTERVAL_MS);
      const next = await invoke("library_import_status", {
        importJobId: snapshot.import_job_id,
      });
      if (!validJobSnapshot(next)) {
        throw new Error("The desktop host returned an invalid import status.");
      }
      if (
        next.import_job_id !== snapshot.import_job_id ||
        !countsDoNotRegress(snapshot.counts, next.counts)
      ) {
        throw new Error("The desktop host returned a regressive import status.");
      }
      snapshot = next;
      renderProgress(snapshot);
    }

    return snapshot;
  }

  async function importLibrary() {
    if (busy || typeof invoke !== "function" || selectedCapability === null) {
      return;
    }

    const capabilityId = selectedCapability.capability_id;
    setBusy(true);
    clearResults();
    clearProgress();
    setStatus("Starting library import…");

    try {
      const initial = await invoke("library_import_start", { capabilityId });
      if (!validJobSnapshot(initial)) {
        throw new Error("The desktop host returned an invalid import job.");
      }
      activeJobId = initial.import_job_id;
      cancelRequested = false;
      updateControls();

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
      activeJobId = null;
      cancelRequested = false;
      setBusy(false);
    }
  }

  async function cancelImport() {
    if (!busy || typeof invoke !== "function" || activeJobId === null || cancelRequested) {
      return;
    }

    cancelRequested = true;
    updateControls();
    setStatus("Cancelling library import…");

    try {
      const snapshot = await invoke("library_import_cancel", {
        importJobId: activeJobId,
      });
      if (!validJobSnapshot(snapshot) || snapshot.import_job_id !== activeJobId) {
        throw new Error("The desktop host returned an invalid cancellation state.");
      }
      renderProgress(snapshot);
      if (snapshot.terminal && snapshot.state !== "cancelled") {
        setStatus("Import had already completed before cancellation.");
      }
    } catch (error) {
      cancelRequested = false;
      updateControls();
      setStatus(errorMessage(error));
    }
  }

  if (typeof invoke !== "function") {
    chooseButton.disabled = true;
    importButton.disabled = true;
    cancelButton.disabled = true;
    setStatus("Desktop bridge unavailable.");
    return;
  }

  chooseButton.addEventListener("click", chooseLibrary);
  importButton.addEventListener("click", importLibrary);
  cancelButton.addEventListener("click", cancelImport);
  setBusy(false);
})();