(() => {
  "use strict";

  const tauriCore = window.__TAURI__?.core;
  const originalInvoke = tauriCore?.invoke;
  const section = document.getElementById("playlist-export");
  const status = document.getElementById("playlist-export-status");
  const revisionSelect = document.getElementById("playlist-export-revision");
  const previewButton = document.getElementById("playlist-export-preview");
  const exportButton = document.getElementById("playlist-export-write");
  const previewNode = document.getElementById("playlist-export-preview-result");
  const receiptNode = document.getElementById("playlist-export-receipt");

  if (
    !section ||
    !status ||
    !revisionSelect ||
    !previewButton ||
    !exportButton ||
    !previewNode ||
    !receiptNode ||
    typeof originalInvoke !== "function"
  ) {
    return;
  }

  const TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,255}$/;
  const OPERATIONS = new Set(["accept", "reorder", "lock", "replace"]);
  let trustedHistory = null;
  let trustedPreview = null;
  let busy = false;

  function exactKeys(value, keys) {
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return false;
    }
    const actual = Object.keys(value).sort();
    const expected = [...keys].sort();
    return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
  }

  function validToken(value) {
    return typeof value === "string" && TOKEN.test(value) && !value.includes("/") && !value.includes("\\");
  }

  function pathShaped(value) {
    return value.startsWith("/") || value.startsWith("\\\\") || /^[A-Za-z]:[\\/]/.test(value);
  }

  function validDisplayName(value) {
    return (
      typeof value === "string" &&
      value.length > 0 &&
      value.length <= 512 &&
      value.trim() === value &&
      !/[\u0000-\u001f\u007f]/.test(value) &&
      !pathShaped(value)
    );
  }

  function validFilename(value) {
    return (
      typeof value === "string" &&
      value.length > 0 &&
      value.length <= 128 &&
      value.endsWith(".m3u8") &&
      value.trim() === value &&
      !value.includes("/") &&
      !value.includes("\\") &&
      !/[\u0000-\u001f\u007f]/.test(value)
    );
  }

  function validRevision(value) {
    if (
      !exactKeys(value, [
        "schema",
        "playlist_id",
        "revision_id",
        "parent_revision_id",
        "revision_index",
        "source_proposal_id",
        "source_path_id",
        "operation",
        "content_fingerprint",
        "created_at",
        "sequence",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) ||
      value.schema !== "applaylist-desktop-playlist-revision-r1" ||
      !validToken(value.playlist_id) ||
      !validToken(value.revision_id) ||
      !(value.parent_revision_id === null || validToken(value.parent_revision_id)) ||
      !Number.isInteger(value.revision_index) ||
      value.revision_index < 0 ||
      !validToken(value.source_proposal_id) ||
      !validToken(value.source_path_id) ||
      !OPERATIONS.has(value.operation) ||
      typeof value.content_fingerprint !== "string" ||
      !/^[0-9a-f]{64}$/.test(value.content_fingerprint) ||
      typeof value.created_at !== "string" ||
      value.created_at.length === 0 ||
      value.created_at.length > 64 ||
      !Array.isArray(value.sequence) ||
      value.sequence.length < 3 ||
      value.sequence.length > 8 ||
      value.personal_dj_model_training_authorized !== false ||
      value.production_activation_authorized !== false
    ) {
      return false;
    }
    const ids = new Set();
    return value.sequence.every((item, index) => {
      if (
        !exactKeys(item, ["order_index", "track_id", "display_name", "locked"]) ||
        item.order_index !== index ||
        !validToken(item.track_id) ||
        !validDisplayName(item.display_name) ||
        typeof item.locked !== "boolean" ||
        ids.has(item.track_id)
      ) {
        return false;
      }
      ids.add(item.track_id);
      return true;
    });
  }

  function validHistory(value) {
    if (
      !exactKeys(value, [
        "schema",
        "playlist_id",
        "current_revision_id",
        "revisions",
        "history_truncated",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) ||
      value.schema !== "applaylist-desktop-playlist-history-r1" ||
      !validToken(value.playlist_id) ||
      !validToken(value.current_revision_id) ||
      !Array.isArray(value.revisions) ||
      value.revisions.length < 1 ||
      value.revisions.length > 100 ||
      value.revisions.some((revision) => !validRevision(revision) || revision.playlist_id !== value.playlist_id) ||
      value.revisions[value.revisions.length - 1].revision_id !== value.current_revision_id ||
      typeof value.history_truncated !== "boolean" ||
      value.personal_dj_model_training_authorized !== false ||
      value.production_activation_authorized !== false
    ) {
      return false;
    }
    return value.revisions.every(
      (revision, index) => index === 0 || revision.revision_index === value.revisions[index - 1].revision_index + 1,
    );
  }

  function validPreview(value) {
    if (
      !exactKeys(value, [
        "schema",
        "revision_id",
        "playlist_id",
        "revision_index",
        "format",
        "suggested_filename",
        "track_count",
        "sequence",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) ||
      value.schema !== "applaylist-desktop-playlist-export-preview-r1" ||
      !validToken(value.revision_id) ||
      !validToken(value.playlist_id) ||
      !Number.isInteger(value.revision_index) ||
      value.revision_index < 0 ||
      value.format !== "m3u8" ||
      !validFilename(value.suggested_filename) ||
      !Number.isInteger(value.track_count) ||
      value.track_count < 3 ||
      value.track_count > 8 ||
      !Array.isArray(value.sequence) ||
      value.sequence.length !== value.track_count ||
      value.personal_dj_model_training_authorized !== false ||
      value.production_activation_authorized !== false
    ) {
      return false;
    }
    const ids = new Set();
    return value.sequence.every((item, index) => {
      if (
        !exactKeys(item, ["order_index", "track_id", "display_name", "locked"]) ||
        item.order_index !== index ||
        !validToken(item.track_id) ||
        !validDisplayName(item.display_name) ||
        typeof item.locked !== "boolean" ||
        ids.has(item.track_id)
      ) {
        return false;
      }
      ids.add(item.track_id);
      return true;
    });
  }

  function validReceipt(value) {
    return (
      exactKeys(value, [
        "revision_id",
        "format",
        "filename",
        "track_count",
        "content_sha256",
        "bytes_written",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) &&
      validToken(value.revision_id) &&
      value.format === "m3u8" &&
      validFilename(value.filename) &&
      Number.isInteger(value.track_count) &&
      value.track_count >= 3 &&
      value.track_count <= 8 &&
      typeof value.content_sha256 === "string" &&
      /^[0-9a-f]{64}$/.test(value.content_sha256) &&
      Number.isInteger(value.bytes_written) &&
      value.bytes_written > 0 &&
      value.bytes_written <= 131072 &&
      value.personal_dj_model_training_authorized === false &&
      value.production_activation_authorized === false
    );
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function setHistory(history) {
    trustedHistory = history;
    trustedPreview = null;
    revisionSelect.replaceChildren();
    for (const revision of history.revisions) {
      const option = document.createElement("option");
      option.value = revision.revision_id;
      option.textContent = `#${revision.revision_index} ${revision.operation} · ${revision.revision_id}`;
      option.selected = revision.revision_id === history.current_revision_id;
      revisionSelect.appendChild(option);
    }
    revisionSelect.disabled = false;
    previewButton.disabled = false;
    exportButton.disabled = true;
    previewNode.replaceChildren();
    receiptNode.replaceChildren();
    setStatus("Choose an immutable revision and preview its M3U8 export.");
  }

  async function observedInvoke(command, args) {
    const result = await originalInvoke(command, args);
    if (command === "playlist_editor_history" && validHistory(result)) {
      setHistory(result);
    }
    return result;
  }

  try {
    tauriCore.invoke = observedInvoke;
  } catch (_error) {
    setStatus("Playlist export history capture is unavailable in this desktop host.");
    return;
  }
  if (tauriCore.invoke !== observedInvoke) {
    setStatus("Playlist export history capture is unavailable in this desktop host.");
    return;
  }

  revisionSelect.addEventListener("change", () => {
    trustedPreview = null;
    exportButton.disabled = true;
    previewNode.replaceChildren();
    receiptNode.replaceChildren();
    setStatus("Preview the selected immutable revision before export.");
  });

  previewButton.addEventListener("click", async () => {
    if (busy || !trustedHistory || !validToken(revisionSelect.value)) {
      return;
    }
    busy = true;
    previewButton.disabled = true;
    exportButton.disabled = true;
    setStatus("Building renderer-safe export preview…");
    try {
      const preview = await originalInvoke("playlist_export_preview", {
        revisionId: revisionSelect.value,
      });
      if (!validPreview(preview) || preview.revision_id !== revisionSelect.value) {
        throw new Error("Invalid export preview response.");
      }
      trustedPreview = preview;
      renderPreview(preview);
      exportButton.disabled = false;
      setStatus("Preview verified. Export writes only after the native save dialog is confirmed.");
    } catch (_error) {
      trustedPreview = null;
      previewNode.replaceChildren();
      setStatus("The selected revision could not be prepared for export safely.");
    } finally {
      busy = false;
      previewButton.disabled = false;
    }
  });

  exportButton.addEventListener("click", async () => {
    if (
      busy ||
      !trustedPreview ||
      trustedPreview.revision_id !== revisionSelect.value ||
      !validToken(revisionSelect.value)
    ) {
      return;
    }
    busy = true;
    previewButton.disabled = true;
    exportButton.disabled = true;
    receiptNode.replaceChildren();
    setStatus("Choose a new .m3u8 file in the native save dialog…");
    try {
      const receipt = await originalInvoke("playlist_export_m3u8", {
        revisionId: revisionSelect.value,
      });
      if (receipt === null) {
        setStatus("Export canceled. No file was written.");
        return;
      }
      if (!validReceipt(receipt) || receipt.revision_id !== revisionSelect.value) {
        throw new Error("Invalid export receipt response.");
      }
      renderReceipt(receipt);
      setStatus("M3U8 export completed from the exact immutable revision.");
    } catch (_error) {
      setStatus("The export was rejected safely. No successful receipt was produced.");
    } finally {
      busy = false;
      previewButton.disabled = false;
      exportButton.disabled = trustedPreview === null;
    }
  });

  function renderPreview(preview) {
    previewNode.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = `Export preview · revision #${preview.revision_index}`;
    const metadata = document.createElement("p");
    metadata.textContent = `${preview.format.toUpperCase()} · ${preview.track_count} tracks · ${preview.suggested_filename}`;
    const list = document.createElement("ol");
    for (const item of preview.sequence) {
      const row = document.createElement("li");
      row.textContent = `${item.display_name}${item.locked ? " · locked" : ""}`;
      list.appendChild(row);
    }
    previewNode.append(heading, metadata, list);
  }

  function renderReceipt(receipt) {
    receiptNode.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = "Export receipt";
    const list = document.createElement("dl");
    for (const [label, value] of [
      ["Revision", receipt.revision_id],
      ["Format", receipt.format],
      ["File", receipt.filename],
      ["Tracks", String(receipt.track_count)],
      ["Bytes", String(receipt.bytes_written)],
      ["SHA-256", receipt.content_sha256],
    ]) {
      const term = document.createElement("dt");
      term.textContent = label;
      const description = document.createElement("dd");
      description.textContent = value;
      list.append(term, description);
    }
    receiptNode.append(heading, list);
  }

  revisionSelect.disabled = true;
  previewButton.disabled = true;
  exportButton.disabled = true;
})();
