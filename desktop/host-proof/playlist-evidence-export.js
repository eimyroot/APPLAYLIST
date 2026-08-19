(() => {
  "use strict";

  const tauriCore = window.__TAURI__?.core;
  const originalInvoke = tauriCore?.invoke;
  const section = document.getElementById("playlist-evidence-export");
  const status = document.getElementById("playlist-evidence-status");
  const revisionSelect = document.getElementById("playlist-evidence-revision");
  const previewButton = document.getElementById("playlist-evidence-preview");
  const exportButton = document.getElementById("playlist-evidence-write");
  const previewNode = document.getElementById("playlist-evidence-preview-result");
  const receiptNode = document.getElementById("playlist-evidence-receipt");

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
  const OPERATIONS = new Set(["accept", "reorder", "lock", "replace", "regenerate"]);
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

  function validJsonFilename(value) {
    return (
      typeof value === "string" &&
      value.length > 0 &&
      value.length <= 128 &&
      value.endsWith(".json") &&
      value.trim() === value &&
      !value.includes("/") &&
      !value.includes("\\") &&
      !/[\u0000-\u001f\u007f]/.test(value)
    );
  }

  function validDigest(value) {
    return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
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
      !validDigest(value.content_fingerprint) ||
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
    return (
      exactKeys(value, [
        "schema",
        "revision_id",
        "playlist_id",
        "revision_index",
        "format",
        "suggested_filename",
        "track_count",
        "analysis_evidence_count",
        "transition_pair_count",
        "transition_evidence_pair_count",
        "m3u8_path_valid",
        "m3u8_content_sha256",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) &&
      value.schema === "applaylist-desktop-playlist-evidence-preview-r1" &&
      validToken(value.revision_id) &&
      validToken(value.playlist_id) &&
      Number.isInteger(value.revision_index) &&
      value.revision_index >= 0 &&
      value.format === "json" &&
      validJsonFilename(value.suggested_filename) &&
      Number.isInteger(value.track_count) &&
      value.track_count >= 3 &&
      value.track_count <= 8 &&
      Number.isInteger(value.analysis_evidence_count) &&
      value.analysis_evidence_count >= 0 &&
      value.analysis_evidence_count <= value.track_count &&
      Number.isInteger(value.transition_pair_count) &&
      value.transition_pair_count === value.track_count - 1 &&
      Number.isInteger(value.transition_evidence_pair_count) &&
      value.transition_evidence_pair_count >= 0 &&
      value.transition_evidence_pair_count <= value.transition_pair_count &&
      value.m3u8_path_valid === true &&
      validDigest(value.m3u8_content_sha256) &&
      value.personal_dj_model_training_authorized === false &&
      value.production_activation_authorized === false
    );
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
        "m3u8_path_valid",
        "m3u8_content_sha256",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) &&
      validToken(value.revision_id) &&
      value.format === "json" &&
      validJsonFilename(value.filename) &&
      Number.isInteger(value.track_count) &&
      value.track_count >= 3 &&
      value.track_count <= 8 &&
      validDigest(value.content_sha256) &&
      Number.isInteger(value.bytes_written) &&
      value.bytes_written > 0 &&
      value.bytes_written <= 262144 &&
      value.m3u8_path_valid === true &&
      validDigest(value.m3u8_content_sha256) &&
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
    setStatus("Choose an immutable revision and preview its JSON evidence companion.");
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
    setStatus("JSON evidence export history capture is unavailable in this desktop host.");
    return;
  }
  if (tauriCore.invoke !== observedInvoke) {
    setStatus("JSON evidence export history capture is unavailable in this desktop host.");
    return;
  }

  revisionSelect.addEventListener("change", () => {
    trustedPreview = null;
    exportButton.disabled = true;
    previewNode.replaceChildren();
    receiptNode.replaceChildren();
    setStatus("Preview the selected immutable revision before JSON evidence export.");
  });

  previewButton.addEventListener("click", async () => {
    if (busy || !trustedHistory || !validToken(revisionSelect.value)) {
      return;
    }
    busy = true;
    previewButton.disabled = true;
    exportButton.disabled = true;
    setStatus("Verifying path state and building evidence preview…");
    try {
      const preview = await originalInvoke("playlist_evidence_preview", {
        revisionId: revisionSelect.value,
      });
      if (!validPreview(preview) || preview.revision_id !== revisionSelect.value) {
        throw new Error("Invalid evidence preview response.");
      }
      trustedPreview = preview;
      renderPreview(preview);
      exportButton.disabled = false;
      setStatus("Evidence preview verified. JSON export remains an explicit local save action.");
    } catch (_error) {
      trustedPreview = null;
      previewNode.replaceChildren();
      setStatus("The selected revision could not produce a path-valid evidence preview.");
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
    setStatus("Choose a new .json file in the native save dialog…");
    try {
      const receipt = await originalInvoke("playlist_evidence_export_json", {
        revisionId: revisionSelect.value,
      });
      if (receipt === null) {
        setStatus("JSON evidence export canceled. No file was written.");
        return;
      }
      if (!validReceipt(receipt) || receipt.revision_id !== revisionSelect.value) {
        throw new Error("Invalid evidence export receipt response.");
      }
      renderReceipt(receipt);
      setStatus("JSON evidence export completed for the exact immutable revision.");
    } catch (_error) {
      setStatus("The JSON evidence export was rejected safely. No successful receipt was produced.");
    } finally {
      busy = false;
      previewButton.disabled = false;
      exportButton.disabled = trustedPreview === null;
    }
  });

  function renderPreview(preview) {
    previewNode.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = `Evidence preview · revision #${preview.revision_index}`;
    const metadata = document.createElement("dl");
    for (const [label, value] of [
      ["File", preview.suggested_filename],
      ["Tracks", String(preview.track_count)],
      ["Analysis evidence", `${preview.analysis_evidence_count}/${preview.track_count}`],
      ["Transition pairs with evidence", `${preview.transition_evidence_pair_count}/${preview.transition_pair_count}`],
      ["M3U8 path verification", preview.m3u8_path_valid ? "valid" : "invalid"],
      ["M3U8 SHA-256", preview.m3u8_content_sha256],
    ]) {
      const term = document.createElement("dt");
      term.textContent = label;
      const description = document.createElement("dd");
      description.textContent = value;
      metadata.append(term, description);
    }
    previewNode.append(heading, metadata);
  }

  function renderReceipt(receipt) {
    receiptNode.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = "JSON evidence receipt";
    const list = document.createElement("dl");
    for (const [label, value] of [
      ["Revision", receipt.revision_id],
      ["File", receipt.filename],
      ["Tracks", String(receipt.track_count)],
      ["Bytes", String(receipt.bytes_written)],
      ["JSON SHA-256", receipt.content_sha256],
      ["M3U8 path verification", receipt.m3u8_path_valid ? "valid" : "invalid"],
      ["M3U8 SHA-256", receipt.m3u8_content_sha256],
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
