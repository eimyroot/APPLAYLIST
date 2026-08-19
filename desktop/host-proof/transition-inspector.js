(() => {
  "use strict";

  const tauriCore = window.__TAURI__?.core;
  const originalInvoke = tauriCore?.invoke;
  const section = document.getElementById("transition-inspector");
  const status = document.getElementById("transition-inspector-status");
  const revisionSelect = document.getElementById("transition-inspector-revision");
  const pairSelect = document.getElementById("transition-inspector-pair");
  const inspectButton = document.getElementById("transition-inspector-load");
  const resultNode = document.getElementById("transition-inspector-result");

  if (
    !section ||
    !status ||
    !revisionSelect ||
    !pairSelect ||
    !inspectButton ||
    !resultNode ||
    typeof originalInvoke !== "function"
  ) {
    return;
  }

  const TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,255}$/;
  const OPERATIONS = new Set(["accept", "reorder", "lock", "replace"]);
  let trustedHistory = null;
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
      !/^[0-9a-f]{64}$/.test(value.content_fingerprint) ||
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
      value.revisions.every(validRevision) &&
      value.revisions[value.revisions.length - 1].revision_id === value.current_revision_id &&
      typeof value.history_truncated === "boolean" &&
      value.personal_dj_model_training_authorized === false &&
      value.production_activation_authorized === false
    );
  }

  function validSnapshot(value) {
    return (
      exactKeys(value, [
        "snapshot_id",
        "transition_id",
        "source_segment_id",
        "target_segment_id",
        "assessment_version",
        "policy_version",
        "context_id",
        "context_version",
        "payload_sha256",
        "created_at",
      ]) &&
      validToken(value.snapshot_id) &&
      validToken(value.transition_id) &&
      validToken(value.source_segment_id) &&
      validToken(value.target_segment_id) &&
      validToken(value.assessment_version) &&
      validToken(value.policy_version) &&
      validToken(value.context_id) &&
      validToken(value.context_version) &&
      /^[0-9a-f]{64}$/.test(value.payload_sha256) &&
      typeof value.created_at === "string" &&
      value.created_at.length > 0 &&
      value.created_at.length <= 64
    );
  }

  function safeObject(value, depth = 0) {
    if (depth > 8) return false;
    if (value === null || typeof value === "boolean" || typeof value === "number") return true;
    if (typeof value === "string") {
      return value.length <= 1024 && !pathShaped(value) && !/[\u0000-\u001f\u007f]/.test(value);
    }
    if (Array.isArray(value)) {
      return value.length <= 128 && value.every((item) => safeObject(item, depth + 1));
    }
    if (typeof value !== "object") return false;
    return Object.entries(value).every(([key, item]) => {
      if (["payload_json", "content_utf8", "source_path", "target_path", "filesystem_path"].includes(key)) {
        return false;
      }
      return safeObject(item, depth + 1);
    });
  }

  function validInspection(value, revisionId, pairIndex) {
    if (
      !exactKeys(value, [
        "schema",
        "revision_id",
        "playlist_id",
        "revision_index",
        "pair_index",
        "source",
        "target",
        "available_snapshots",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
        "transition_recomputation_authorized",
        "playlist_mutation_authorized",
        "state",
        "selected_snapshot_id",
        "assessment",
      ]) ||
      value.schema !== "applaylist-desktop-transition-inspection-r1" ||
      value.revision_id !== revisionId ||
      !validToken(value.playlist_id) ||
      value.pair_index !== pairIndex ||
      !Number.isInteger(value.revision_index) ||
      value.revision_index < 0 ||
      !exactKeys(value.source, ["order_index", "track_id", "display_name", "locked"]) ||
      !exactKeys(value.target, ["order_index", "track_id", "display_name", "locked"]) ||
      value.source.order_index !== pairIndex ||
      value.target.order_index !== pairIndex + 1 ||
      !validToken(value.source.track_id) ||
      !validToken(value.target.track_id) ||
      !validDisplayName(value.source.display_name) ||
      !validDisplayName(value.target.display_name) ||
      typeof value.source.locked !== "boolean" ||
      typeof value.target.locked !== "boolean" ||
      !Array.isArray(value.available_snapshots) ||
      value.available_snapshots.length > 16 ||
      !value.available_snapshots.every(validSnapshot) ||
      value.personal_dj_model_training_authorized !== false ||
      value.production_activation_authorized !== false ||
      value.transition_recomputation_authorized !== false ||
      value.playlist_mutation_authorized !== false
    ) {
      return false;
    }
    if (value.state === "missing") {
      return value.available_snapshots.length === 0 && value.selected_snapshot_id === null && value.assessment === null;
    }
    return (
      value.state === "present" &&
      value.available_snapshots.length > 0 &&
      validToken(value.selected_snapshot_id) &&
      value.available_snapshots[0].snapshot_id === value.selected_snapshot_id &&
      value.assessment !== null &&
      typeof value.assessment === "object" &&
      !Array.isArray(value.assessment) &&
      safeObject(value.assessment)
    );
  }

  function selectedRevision() {
    if (!trustedHistory) return null;
    return trustedHistory.revisions.find((revision) => revision.revision_id === revisionSelect.value) || null;
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function populatePairs() {
    pairSelect.replaceChildren();
    resultNode.replaceChildren();
    const revision = selectedRevision();
    if (!revision) {
      pairSelect.disabled = true;
      inspectButton.disabled = true;
      return;
    }
    for (let index = 0; index < revision.sequence.length - 1; index += 1) {
      const source = revision.sequence[index];
      const target = revision.sequence[index + 1];
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = `${index + 1}. ${source.display_name} → ${target.display_name}`;
      pairSelect.appendChild(option);
    }
    pairSelect.disabled = false;
    inspectButton.disabled = false;
    setStatus("Choose one adjacent transition from the immutable revision.");
  }

  function setHistory(history) {
    trustedHistory = history;
    revisionSelect.replaceChildren();
    for (const revision of history.revisions) {
      const option = document.createElement("option");
      option.value = revision.revision_id;
      option.textContent = `#${revision.revision_index} ${revision.operation} · ${revision.revision_id}`;
      option.selected = revision.revision_id === history.current_revision_id;
      revisionSelect.appendChild(option);
    }
    revisionSelect.disabled = false;
    populatePairs();
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
    setStatus("Transition inspection history capture is unavailable in this desktop host.");
    return;
  }
  if (tauriCore.invoke !== observedInvoke) {
    setStatus("Transition inspection history capture is unavailable in this desktop host.");
    return;
  }

  revisionSelect.addEventListener("change", populatePairs);
  pairSelect.addEventListener("change", () => {
    resultNode.replaceChildren();
    setStatus("Inspect the selected persisted transition evidence.");
  });

  inspectButton.addEventListener("click", async () => {
    if (busy) return;
    const revision = selectedRevision();
    const pairIndex = Number.parseInt(pairSelect.value, 10);
    if (!revision || !Number.isInteger(pairIndex) || pairIndex < 0 || pairIndex >= revision.sequence.length - 1) {
      return;
    }
    busy = true;
    inspectButton.disabled = true;
    resultNode.replaceChildren();
    setStatus("Loading persisted TransitionAssessment evidence…");
    try {
      const inspection = await originalInvoke("playlist_transition_inspect", {
        revisionId: revision.revision_id,
        pairIndex,
      });
      if (!validInspection(inspection, revision.revision_id, pairIndex)) {
        throw new Error("Invalid transition inspection response.");
      }
      renderInspection(inspection);
      setStatus(
        inspection.state === "present"
          ? "Persisted transition evidence loaded. No recomputation was performed."
          : "No persisted TransitionAssessment exists for this adjacent pair.",
      );
    } catch (_error) {
      resultNode.replaceChildren();
      setStatus("Transition inspection was rejected safely.");
    } finally {
      busy = false;
      inspectButton.disabled = false;
    }
  });

  function addMetric(list, label, value) {
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value === null || value === undefined ? "—" : String(value);
    list.append(term, description);
  }

  function renderInspection(inspection) {
    resultNode.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = `${inspection.source.display_name} → ${inspection.target.display_name}`;
    resultNode.appendChild(heading);

    if (inspection.state === "missing") {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No persisted TransitionAssessment snapshot is available for this pair.";
      resultNode.appendChild(empty);
      return;
    }

    const assessment = inspection.assessment;
    const summary = document.createElement("dl");
    summary.className = "summary-grid";
    addMetric(summary, "Snapshot", inspection.selected_snapshot_id);
    addMetric(summary, "Transition", assessment.transition_id);
    addMetric(summary, "Context", `${assessment.contextual_projection.context_id} · ${assessment.contextual_projection.context_version}`);
    addMetric(summary, "Context score", assessment.contextual_projection.score);
    addMetric(summary, "Preferred strategy", assessment.preferred_strategy || "none");
    addMetric(summary, "Tempo fit", assessment.compatibility.tempo_fit);
    addMetric(summary, "Phrase fit", assessment.compatibility.phrase_fit);
    addMetric(summary, "Harmonic fit", assessment.compatibility.harmonic_fit);
    addMetric(summary, "Risk uncertainty", assessment.risk.uncertainty);
    addMetric(summary, "Energy direction", assessment.energy_effect.direction);
    addMetric(summary, "Overall confidence", assessment.confidence.score);
    resultNode.appendChild(summary);

    const strategiesHeading = document.createElement("h4");
    strategiesHeading.textContent = "Candidate strategies";
    const strategies = document.createElement("ol");
    for (const item of assessment.candidate_strategies) {
      const row = document.createElement("li");
      row.textContent = `${item.strategy} · suitability ${item.suitability}`;
      strategies.appendChild(row);
    }
    resultNode.append(strategiesHeading, strategies);

    const evidenceHeading = document.createElement("h4");
    evidenceHeading.textContent = "Evidence references";
    const evidence = document.createElement("ul");
    for (const ref of assessment.evidence_refs) {
      const row = document.createElement("li");
      row.textContent = ref;
      evidence.appendChild(row);
    }
    resultNode.append(evidenceHeading, evidence);
  }

  revisionSelect.disabled = true;
  pairSelect.disabled = true;
  inspectButton.disabled = true;
})();
