(() => {
  "use strict";

  const chooseButton = document.getElementById("choose-library");
  const importButton = document.getElementById("import-library");
  const selectedLibrary = document.getElementById("selected-library");
  const status = document.getElementById("status");
  const summary = document.getElementById("import-summary");
  const summaryLibrary = document.getElementById("summary-library");
  const summaryDiscovered = document.getElementById("summary-discovered");
  const summaryAccepted = document.getElementById("summary-accepted");
  const summaryImported = document.getElementById("summary-imported");
  const summaryPersisted = document.getElementById("summary-persisted");
  const summaryIssues = document.getElementById("summary-issues");

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
      Array.isArray(value.issues) &&
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

  function renderImportSummary(result) {
    summaryLibrary.textContent = result.folder_name;
    summaryDiscovered.textContent = String(result.counts.discovered_entries);
    summaryAccepted.textContent = String(result.counts.accepted);
    summaryImported.textContent = String(result.counts.imported);
    summaryPersisted.textContent = String(result.counts.persisted);
    summaryIssues.textContent = String(result.issues.length);
    summary.hidden = false;
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
      summary.hidden = true;
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
      if (result.cancelled) {
        setStatus("Import cancelled.");
      } else if (result.complete) {
        setStatus(`Import complete. ${result.counts.persisted} tracks persisted.`);
      } else {
        setStatus("Import stopped before completion.");
      }
    } catch (error) {
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
