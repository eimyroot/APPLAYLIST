(() => {
  "use strict";

  const chooseButton = document.getElementById("choose-library");
  const importButton = document.getElementById("import-library");
  const importSection = document.getElementById("library-import");
  const selectedLibrary = document.getElementById("selected-library");
  const status = document.getElementById("status");
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
  let busy = false;

  function setStatus(message) {
    status.textContent = message;
  }

  function setBusy(nextBusy) {
    busy = nextBusy;
    chooseButton.disabled = nextBusy;
    importButton.disabled = nextBusy || selectedCapability === null;
    importSection.setAttribute("aria-busy", nextBusy ? "true" : "false");
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
      value.counts !== null &&
      typeof value.counts === "object" &&
      Number.isInteger(value.counts.discovered_entries) &&
      Number.isInteger(value.counts.accepted) &&
      Number.isInteger(value.counts.imported) &&
      Number.isInteger(value.counts.persisted) &&
      Array.isArray(value.tracks) &&
      value.tracks.every(validTrack) &&
      Array.isArray(value.issues) &&
      value.issues.every(validIssue) &&
      typeof value.complete === "boolean" &&
      typeof value.cancelled === "boolean"
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
      setStatus("Library selected. Ready to import.");
    } catch (error) {
      setStatus(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function importLibrary() {
    if (busy || typeof invoke !== "function" || selectedCapability === null) {
      return;
    }

    const capabilityId = selectedCapability.capability_id;
    setBusy(true);
    setStatus("Importing library…");

    try {
      const result = await invoke("library_import_root", { capabilityId });
      if (!validImportResult(result)) {
        throw new Error("The desktop host returned an invalid import result.");
      }

      renderImportSummary(result);
      renderLibraryTracks(result.tracks);
      renderIssues(result.issues);

      if (result.cancelled) {
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
      setBusy(false);
    }
  }

  if (typeof invoke !== "function") {
    chooseButton.disabled = true;
    importButton.disabled = true;
    setStatus("Desktop bridge unavailable.");
    return;
  }

  chooseButton.addEventListener("click", chooseLibrary);
  importButton.addEventListener("click", importLibrary);
  setBusy(false);
})();
