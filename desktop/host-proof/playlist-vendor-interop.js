(() => {
  "use strict";

  const tauriCore = window.__TAURI__?.core;
  const originalInvoke = tauriCore?.invoke;
  const section = document.getElementById("playlist-vendor-interop");
  const status = document.getElementById("playlist-vendor-interop-status");
  const revisionSelect = document.getElementById("playlist-vendor-interop-revision");
  const previewButton = document.getElementById("playlist-vendor-interop-preview");
  const rekordboxButton = document.getElementById("playlist-vendor-interop-rekordbox");
  const capabilityNode = document.getElementById("playlist-vendor-interop-capabilities");
  const receiptNode = document.getElementById("playlist-vendor-interop-receipt");

  if (
    !section ||
    !status ||
    !revisionSelect ||
    !previewButton ||
    !rekordboxButton ||
    !capabilityNode ||
    !receiptNode ||
    typeof originalInvoke !== "function"
  ) {
    return;
  }

  const TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,255}$/;
  const DIGEST = /^[0-9a-f]{64}$/;
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

  function validHistory(value) {
    return (
      exactKeys(value, [
        "schema",
        "playlist_id",
        "current_revision_id",
        "revisions",
        "history_truncated",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) &&
      value.schema === "applaylist-desktop-playlist-history-r1" &&
      validToken(value.playlist_id) &&
      validToken(value.current_revision_id) &&
      Array.isArray(value.revisions) &&
      value.revisions.length >= 1 &&
      value.revisions.length <= 100 &&
      value.personal_dj_model_training_authorized === false &&
      value.production_activation_authorized === false &&
      value.revisions.every(
        (revision) =>
          revision !== null &&
          typeof revision === "object" &&
          !Array.isArray(revision) &&
          validToken(revision.revision_id) &&
          Number.isInteger(revision.revision_index) &&
          revision.revision_index >= 0,
      )
    );
  }

  function validCapability(value, expected) {
    return (
      exactKeys(value, [
        "vendor",
        "status",
        "artifact_format",
        "source_reference_code",
        "user_action_code",
        "artifact_export_available",
        "vendor_database_mutation_authorized",
      ]) &&
      value.vendor === expected.vendor &&
      value.status === expected.status &&
      value.artifact_format === expected.artifactFormat &&
      value.source_reference_code === expected.sourceReferenceCode &&
      value.user_action_code === expected.userActionCode &&
      value.artifact_export_available === expected.artifactExportAvailable &&
      value.vendor_database_mutation_authorized === false
    );
  }

  function validPreview(value) {
    if (
      !exactKeys(value, [
        "schema",
        "catalog_version",
        "verified_at",
        "revision_id",
        "playlist_id",
        "revision_index",
        "track_count",
        "m3u8_path_valid",
        "m3u8_content_sha256",
        "capabilities",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) ||
      value.schema !== "applaylist-desktop-vendor-interop-preview-r1" ||
      value.catalog_version !== "vendor-interop-catalog-r1" ||
      value.verified_at !== "2026-08-19" ||
      !validToken(value.revision_id) ||
      !validToken(value.playlist_id) ||
      !Number.isInteger(value.revision_index) ||
      value.revision_index < 0 ||
      !Number.isInteger(value.track_count) ||
      value.track_count < 3 ||
      value.track_count > 8 ||
      value.m3u8_path_valid !== true ||
      typeof value.m3u8_content_sha256 !== "string" ||
      !DIGEST.test(value.m3u8_content_sha256) ||
      !Array.isArray(value.capabilities) ||
      value.capabilities.length !== 3 ||
      value.personal_dj_model_training_authorized !== false ||
      value.production_activation_authorized !== false
    ) {
      return false;
    }
    const expected = [
      {
        vendor: "rekordbox",
        status: "documented_format_export",
        artifactFormat: "rekordbox_xml",
        sourceReferenceCode: "rekordbox_xml_bridge_official",
        userActionCode: "import_xml_via_bridge",
        artifactExportAvailable: true,
      },
      {
        vendor: "traktor",
        status: "guidance_only_nml_required",
        artifactFormat: null,
        sourceReferenceCode: "traktor_nml_import_official",
        userActionCode: "use_supported_nml_import_workflow",
        artifactExportAvailable: false,
      },
      {
        vendor: "serato",
        status: "guidance_only_files_crate",
        artifactFormat: null,
        sourceReferenceCode: "serato_files_crate_official",
        userActionCode: "drag_files_or_folder_to_crate",
        artifactExportAvailable: false,
      },
    ];
    return value.capabilities.every((capability, index) => validCapability(capability, expected[index]));
  }

  function validFilename(value) {
    return (
      typeof value === "string" &&
      value.length > 0 &&
      value.length <= 128 &&
      value.endsWith(".xml") &&
      value.trim() === value &&
      !value.includes("/") &&
      !value.includes("\\") &&
      !/[\u0000-\u001f\u007f]/.test(value)
    );
  }

  function validReceipt(value) {
    return (
      exactKeys(value, [
        "revision_id",
        "vendor",
        "format",
        "filename",
        "track_count",
        "content_sha256",
        "bytes_written",
        "m3u8_content_sha256",
        "vendor_database_mutation_authorized",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) &&
      validToken(value.revision_id) &&
      value.vendor === "rekordbox" &&
      value.format === "rekordbox_xml" &&
      validFilename(value.filename) &&
      Number.isInteger(value.track_count) &&
      value.track_count >= 3 &&
      value.track_count <= 8 &&
      typeof value.content_sha256 === "string" &&
      DIGEST.test(value.content_sha256) &&
      Number.isInteger(value.bytes_written) &&
      value.bytes_written > 0 &&
      value.bytes_written <= 131072 &&
      typeof value.m3u8_content_sha256 === "string" &&
      DIGEST.test(value.m3u8_content_sha256) &&
      value.vendor_database_mutation_authorized === false &&
      value.personal_dj_model_training_authorized === false &&
      value.production_activation_authorized === false
    );
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function setHistory(history) {
    trustedPreview = null;
    revisionSelect.replaceChildren();
    for (const revision of history.revisions) {
      const option = document.createElement("option");
      option.value = revision.revision_id;
      option.textContent = `#${revision.revision_index} · ${revision.revision_id}`;
      option.selected = revision.revision_id === history.current_revision_id;
      revisionSelect.appendChild(option);
    }
    revisionSelect.disabled = false;
    previewButton.disabled = false;
    rekordboxButton.disabled = true;
    capabilityNode.replaceChildren();
    receiptNode.replaceChildren();
    setStatus("Choose an immutable revision and verify vendor handoff capabilities.");
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
    setStatus("Vendor handoff revision capture is unavailable in this desktop host.");
    return;
  }
  if (tauriCore.invoke !== observedInvoke) {
    setStatus("Vendor handoff revision capture is unavailable in this desktop host.");
    return;
  }

  revisionSelect.addEventListener("change", () => {
    trustedPreview = null;
    rekordboxButton.disabled = true;
    capabilityNode.replaceChildren();
    receiptNode.replaceChildren();
    setStatus("Preview the selected immutable revision before vendor handoff.");
  });

  previewButton.addEventListener("click", async () => {
    if (busy || !validToken(revisionSelect.value)) {
      return;
    }
    busy = true;
    previewButton.disabled = true;
    rekordboxButton.disabled = true;
    setStatus("Verifying canonical M3U8 path validity and vendor capabilities…");
    try {
      const preview = await originalInvoke("playlist_vendor_interop_preview", {
        revisionId: revisionSelect.value,
      });
      if (!validPreview(preview) || preview.revision_id !== revisionSelect.value) {
        throw new Error("Invalid vendor interoperability preview.");
      }
      trustedPreview = preview;
      renderCapabilities(preview);
      rekordboxButton.disabled = false;
      setStatus("Capabilities verified. Only the documented rekordbox XML artifact is writable in R1.");
    } catch (_error) {
      trustedPreview = null;
      capabilityNode.replaceChildren();
      setStatus("Vendor handoff verification failed safely.");
    } finally {
      busy = false;
      previewButton.disabled = false;
    }
  });

  rekordboxButton.addEventListener("click", async () => {
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
    rekordboxButton.disabled = true;
    receiptNode.replaceChildren();
    setStatus("Choose a new rekordbox XML file in the native save dialog…");
    try {
      const receipt = await originalInvoke("playlist_vendor_interop_export_rekordbox", {
        revisionId: revisionSelect.value,
      });
      if (receipt === null) {
        setStatus("Vendor export canceled. No file was written.");
        return;
      }
      if (!validReceipt(receipt) || receipt.revision_id !== revisionSelect.value) {
        throw new Error("Invalid vendor export receipt.");
      }
      renderReceipt(receipt);
      setStatus("rekordbox XML handoff exported from the exact immutable revision.");
    } catch (_error) {
      setStatus("The rekordbox XML export was rejected safely.");
    } finally {
      busy = false;
      previewButton.disabled = false;
      rekordboxButton.disabled = trustedPreview === null;
    }
  });

  function renderCapabilities(preview) {
    capabilityNode.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = `Vendor handoff · revision #${preview.revision_index}`;
    const summary = document.createElement("p");
    summary.textContent = `${preview.track_count} tracks · canonical M3U8 path verification passed`;
    const list = document.createElement("ul");
    for (const capability of preview.capabilities) {
      const row = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = capability.vendor;
      const detail = document.createElement("span");
      if (capability.vendor === "rekordbox") {
        detail.textContent = " · documented XML Bridge artifact available";
      } else if (capability.vendor === "traktor") {
        detail.textContent = " · guidance only: the documented import workflow requires NML";
      } else {
        detail.textContent = " · guidance only: use the documented file/folder → crate workflow";
      }
      row.append(title, detail);
      list.appendChild(row);
    }
    capabilityNode.append(heading, summary, list);
  }

  function renderReceipt(receipt) {
    receiptNode.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = "Vendor export receipt";
    const list = document.createElement("dl");
    for (const [label, value] of [
      ["Revision", receipt.revision_id],
      ["Vendor", receipt.vendor],
      ["Format", receipt.format],
      ["File", receipt.filename],
      ["Tracks", String(receipt.track_count)],
      ["Bytes", String(receipt.bytes_written)],
      ["XML SHA-256", receipt.content_sha256],
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
  rekordboxButton.disabled = true;
})();