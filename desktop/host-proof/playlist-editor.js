(() => {
  "use strict";

  const tauriCore = window.__TAURI__?.core;
  const originalInvoke = tauriCore?.invoke;
  const section = document.getElementById("playlist-editor");
  const status = document.getElementById("playlist-editor-status");
  const source = document.getElementById("playlist-editor-source");
  const current = document.getElementById("playlist-editor-current");
  const historyNode = document.getElementById("playlist-editor-history");

  if (!section || !status || !source || !current || !historyNode || typeof originalInvoke !== "function") {
    return;
  }

  const TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,255}$/;
  const OPERATIONS = new Set(["accept", "reorder", "lock", "replace", "regenerate"]);
  let lastProposal = null;
  let activeRevision = null;
  let replacementTracks = new Map();
  let regenerationPreview = null;
  let regenerationCandidateIds = [];
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

  function validProposalContext(command, args, proposal) {
    if (command !== "set_proposal_generate" || args === null || typeof args !== "object") {
      return false;
    }
    if (
      !Array.isArray(args.trackIds) ||
      args.trackIds.length < 3 ||
      args.trackIds.length > 24 ||
      !args.trackIds.every(validToken) ||
      new Set(args.trackIds).size !== args.trackIds.length ||
      !validToken(args.seedTrackId) ||
      !args.trackIds.includes(args.seedTrackId) ||
      !Number.isInteger(args.targetTrackCount) ||
      args.targetTrackCount < 3 ||
      args.targetTrackCount > 8 ||
      args.targetTrackCount > args.trackIds.length
    ) {
      return false;
    }
    return (
      proposal !== null &&
      typeof proposal === "object" &&
      proposal.schema === "applaylist-desktop-set-proposal-r1" &&
      validToken(proposal.proposal_id) &&
      Array.isArray(proposal.alternatives) &&
      proposal.alternatives.length <= 3 &&
      proposal.activation_authorized === false &&
      proposal.personal_dj_model_training_authorized === false
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
    if ((value.revision_index === 0) !== (value.parent_revision_id === null && value.operation === "accept")) {
      return false;
    }
    const ids = new Set();
    for (let index = 0; index < value.sequence.length; index += 1) {
      const step = value.sequence[index];
      if (
        !exactKeys(step, ["order_index", "track_id", "display_name", "locked"]) ||
        step.order_index !== index ||
        !validToken(step.track_id) ||
        !validDisplayName(step.display_name) ||
        typeof step.locked !== "boolean" ||
        ids.has(step.track_id)
      ) {
        return false;
      }
      ids.add(step.track_id);
    }
    return true;
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
      value.revisions.some((item) => !validRevision(item) || item.playlist_id !== value.playlist_id) ||
      value.revisions[value.revisions.length - 1].revision_id !== value.current_revision_id ||
      typeof value.history_truncated !== "boolean" ||
      value.personal_dj_model_training_authorized !== false ||
      value.production_activation_authorized !== false
    ) {
      return false;
    }
    for (let index = 1; index < value.revisions.length; index += 1) {
      if (value.revisions[index].revision_index !== value.revisions[index - 1].revision_index + 1) {
        return false;
      }
    }
    return true;
  }

  function validInspectorTrack(value) {
    return (
      value !== null &&
      typeof value === "object" &&
      validToken(value.track_id) &&
      typeof value.title === "string" &&
      value.title.trim().length > 0 &&
      !pathShaped(value.title) &&
      (value.artist === null ||
        (typeof value.artist === "string" && value.artist.trim().length > 0 && !pathShaped(value.artist))) &&
      value.status === "succeeded"
    );
  }

  function validRegenerationPreview(value, revisionId, candidateIds) {
    if (
      !exactKeys(value, [
        "schema",
        "playlist_id",
        "parent_revision_id",
        "regeneration_id",
        "candidate_pool_count",
        "candidate_pool_sha256",
        "locked_positions",
        "alternatives",
        "reason_codes",
        "warning_codes",
        "budget_exhausted",
        "missing_evidence_detected",
        "deterministic_ordering",
        "playlist_mutation_authorized",
        "personal_dj_model_training_authorized",
        "production_activation_authorized",
      ]) ||
      value.schema !== "applaylist-desktop-playlist-regeneration-r1" ||
      !validToken(value.playlist_id) ||
      value.parent_revision_id !== revisionId ||
      !validToken(value.regeneration_id) ||
      value.candidate_pool_count !== candidateIds.length ||
      !/^[0-9a-f]{64}$/.test(value.candidate_pool_sha256) ||
      !Array.isArray(value.locked_positions) ||
      value.locked_positions.length < 1 ||
      value.locked_positions.length > 8 ||
      !Array.isArray(value.alternatives) ||
      value.alternatives.length > 3 ||
      !Array.isArray(value.reason_codes) ||
      !value.reason_codes.every(validToken) ||
      !Array.isArray(value.warning_codes) ||
      !value.warning_codes.every(validToken) ||
      typeof value.budget_exhausted !== "boolean" ||
      typeof value.missing_evidence_detected !== "boolean" ||
      value.deterministic_ordering !== true ||
      value.playlist_mutation_authorized !== false ||
      value.personal_dj_model_training_authorized !== false ||
      value.production_activation_authorized !== false
    ) {
      return false;
    }
    const expectedLocks = activeRevision.sequence
      .filter((item) => item.locked)
      .map((item) => ({ order_index: item.order_index, track_id: item.track_id }));
    if (
      expectedLocks.length !== value.locked_positions.length ||
      expectedLocks.some((lock, index) =>
        !exactKeys(value.locked_positions[index], ["order_index", "track_id"]) ||
        value.locked_positions[index].order_index !== lock.order_index ||
        value.locked_positions[index].track_id !== lock.track_id,
      )
    ) {
      return false;
    }
    return value.alternatives.every((alternative, alternativeIndex) => {
      if (
        !exactKeys(alternative, ["path_id", "rank", "sequence", "objective", "explanation_codes"]) ||
        !validToken(alternative.path_id) ||
        alternative.rank !== alternativeIndex + 1 ||
        !Array.isArray(alternative.sequence) ||
        alternative.sequence.length !== activeRevision.sequence.length ||
        !Array.isArray(alternative.explanation_codes) ||
        !alternative.explanation_codes.every(validToken) ||
        !exactKeys(alternative.objective, [
          "depth",
          "mean_candidate_score",
          "minimum_candidate_score",
          "required_track_completion",
          "remaining_required_count",
          "target_reached",
        ])
      ) {
        return false;
      }
      const ids = new Set();
      return alternative.sequence.every((step, index) => {
        const locked = activeRevision.sequence[index].locked;
        return (
          exactKeys(step, ["order_index", "track_id", "display_name", "locked"]) &&
          step.order_index === index &&
          validToken(step.track_id) &&
          validDisplayName(step.display_name) &&
          step.locked === locked &&
          (!locked || step.track_id === activeRevision.sequence[index].track_id) &&
          !ids.has(step.track_id) &&
          ids.add(step.track_id)
        );
      });
    });
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function clearSource() {
    source.replaceChildren();
  }

  function captureProposal(args, proposal) {
    lastProposal = {
      request: {
        trackIds: [...args.trackIds],
        seedTrackId: args.seedTrackId,
        targetTrackCount: args.targetTrackCount,
      },
      proposal,
    };
    renderProposalChoices();
  }

  async function observedInvoke(command, args) {
    const result = await originalInvoke(command, args);
    if (validProposalContext(command, args, result)) {
      captureProposal(args, result);
    }
    if (command === "playlist_editor_regeneration_apply" && validRevision(result)) {
      activeRevision = result;
      regenerationPreview = null;
      regenerationCandidateIds = [];
      await refreshReplacementTracks();
      await refreshHistory();
      setStatus("Regeneration appended as a new immutable revision.");
    }
    return result;
  }

  try {
    tauriCore.invoke = observedInvoke;
  } catch (_error) {
    setStatus("Manual editor proposal capture is unavailable in this desktop host.");
    return;
  }
  if (tauriCore.invoke !== observedInvoke) {
    setStatus("Manual editor proposal capture is unavailable in this desktop host.");
    return;
  }

  function renderProposalChoices() {
    clearSource();
    if (!lastProposal || lastProposal.proposal.alternatives.length === 0) {
      const message = document.createElement("p");
      message.textContent = "Generate a reviewable Set Proposal first.";
      source.appendChild(message);
      return;
    }
    const heading = document.createElement("h3");
    heading.textContent = `Proposal ${lastProposal.proposal.proposal_id}`;
    source.appendChild(heading);
    for (const alternative of lastProposal.proposal.alternatives) {
      if (!validToken(alternative.path_id) || !Array.isArray(alternative.sequence)) {
        continue;
      }
      const card = document.createElement("article");
      card.className = "editor-proposal-choice";
      const title = document.createElement("h4");
      title.textContent = `Alternative ${alternative.rank}`;
      const list = document.createElement("ol");
      for (const step of alternative.sequence) {
        if (!validDisplayName(step.display_name)) {
          continue;
        }
        const item = document.createElement("li");
        item.textContent = step.display_name;
        list.appendChild(item);
      }
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Accept and open in editor";
      button.addEventListener("click", () => acceptAlternative(alternative.path_id));
      card.append(title, list, button);
      source.appendChild(card);
    }
    setStatus("Choose one proposal alternative to create an immutable root revision.");
  }

  async function acceptAlternative(pathId) {
    if (busy || !lastProposal || !validToken(pathId)) {
      return;
    }
    busy = true;
    setStatus("Verifying proposal identity and creating immutable root revision…");
    try {
      const revision = await originalInvoke("playlist_editor_accept", {
        trackIds: lastProposal.request.trackIds,
        seedTrackId: lastProposal.request.seedTrackId,
        targetTrackCount: lastProposal.request.targetTrackCount,
        proposalId: lastProposal.proposal.proposal_id,
        pathId,
      });
      if (!validRevision(revision)) {
        throw new Error("Invalid playlist revision response.");
      }
      activeRevision = revision;
      await refreshReplacementTracks();
      await refreshHistory();
      setStatus("Root playlist revision accepted. Further edits append new revisions.");
    } catch (_error) {
      setStatus("The proposal could not be accepted safely. Regenerate it if the evidence changed.");
    } finally {
      busy = false;
    }
  }

  async function refreshReplacementTracks() {
    try {
      const response = await originalInvoke("analysis_inspector_list", { filter: "all" });
      if (response === null || typeof response !== "object" || !Array.isArray(response.items)) {
        replacementTracks = new Map();
        return;
      }
      replacementTracks = new Map(
        response.items
          .filter(validInspectorTrack)
          .map((track) => [track.track_id, track.artist ? `${track.artist} — ${track.title}` : track.title]),
      );
    } catch (_error) {
      replacementTracks = new Map();
    }
  }

  async function refreshHistory() {
    if (!activeRevision) {
      return;
    }
    const response = await originalInvoke("playlist_editor_history", {
      playlistId: activeRevision.playlist_id,
    });
    if (!validHistory(response)) {
      throw new Error("Invalid playlist history response.");
    }
    activeRevision = response.revisions[response.revisions.length - 1];
    renderCurrentRevision();
    renderHistory(response);
  }

  function renderCurrentRevision() {
    current.replaceChildren();
    if (!activeRevision) {
      const message = document.createElement("p");
      message.textContent = "No playlist revision is open.";
      current.appendChild(message);
      return;
    }

    const heading = document.createElement("h3");
    heading.textContent = `Revision ${activeRevision.revision_index} · ${activeRevision.revision_id}`;
    const meta = document.createElement("p");
    meta.textContent = `Operation: ${activeRevision.operation} · Parent: ${activeRevision.parent_revision_id ?? "root"}`;
    current.append(heading, meta);

    const list = document.createElement("ol");
    list.className = "editor-sequence";
    for (let index = 0; index < activeRevision.sequence.length; index += 1) {
      const step = activeRevision.sequence[index];
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = step.display_name;

      const lockLabel = document.createElement("label");
      const lock = document.createElement("input");
      lock.type = "checkbox";
      lock.checked = step.locked;
      lock.disabled = busy;
      lock.addEventListener("change", () => changeLock(step.track_id, lock.checked));
      lockLabel.append(lock, document.createTextNode(" Lock"));

      const up = document.createElement("button");
      up.type = "button";
      up.textContent = "↑";
      up.disabled = busy || step.locked || index === 0 || activeRevision.sequence[index - 1].locked;
      up.addEventListener("click", () => moveTrack(index, index - 1));

      const down = document.createElement("button");
      down.type = "button";
      down.textContent = "↓";
      down.disabled =
        busy ||
        step.locked ||
        index === activeRevision.sequence.length - 1 ||
        activeRevision.sequence[index + 1].locked;
      down.addEventListener("click", () => moveTrack(index, index + 1));

      const select = document.createElement("select");
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Replacement…";
      select.appendChild(placeholder);
      const members = new Set(activeRevision.sequence.map((entry) => entry.track_id));
      for (const [trackId, label] of [...replacementTracks.entries()].sort((a, b) => a[1].localeCompare(b[1]))) {
        if (members.has(trackId)) {
          continue;
        }
        const option = document.createElement("option");
        option.value = trackId;
        option.textContent = label;
        select.appendChild(option);
      }
      select.disabled = busy || step.locked;

      const replace = document.createElement("button");
      replace.type = "button";
      replace.textContent = "Replace";
      replace.disabled = busy || step.locked;
      replace.addEventListener("click", () => replaceTrack(step.track_id, select.value));

      item.append(name, lockLabel, up, down, select, replace);
      list.appendChild(item);
    }
    current.appendChild(list);
    renderRegenerationControls();
  }

  function renderRegenerationControls() {
    if (!activeRevision) return;
    const panel = document.createElement("section");
    panel.className = "editor-regeneration";
    const heading = document.createElement("h4");
    heading.textContent = "Regenerate around locks";
    const explanation = document.createElement("p");
    explanation.textContent =
      "R1 preserves locked positions exactly and regenerates only unlocked positions from an explicit analyzed-track pool. Position 1 must be locked.";
    panel.append(heading, explanation);

    const firstLocked = activeRevision.sequence[0]?.locked === true;
    if (!firstLocked) {
      const blocker = document.createElement("p");
      blocker.className = "empty-state";
      blocker.textContent = "Lock the first playlist track before regeneration R1 can run.";
      panel.appendChild(blocker);
      current.appendChild(panel);
      return;
    }

    const currentIds = new Set(activeRevision.sequence.map((item) => item.track_id));
    const lockedIds = new Set(activeRevision.sequence.filter((item) => item.locked).map((item) => item.track_id));
    const candidates = new Map(activeRevision.sequence.map((item) => [item.track_id, item.display_name]));
    for (const [trackId, label] of replacementTracks.entries()) {
      candidates.set(trackId, label);
    }

    const list = document.createElement("div");
    list.className = "regeneration-candidate-list";
    for (const [trackId, label] of [...candidates.entries()].sort((a, b) => a[1].localeCompare(b[1]))) {
      const row = document.createElement("label");
      row.className = "regeneration-candidate";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = trackId;
      checkbox.checked = currentIds.has(trackId);
      checkbox.disabled = lockedIds.has(trackId) || busy;
      if (lockedIds.has(trackId)) checkbox.checked = true;
      checkbox.addEventListener("change", () => {
        regenerationPreview = null;
        regenerationCandidateIds = [];
        renderRegenerationResults(results);
      });
      row.append(checkbox, document.createTextNode(` ${label}${lockedIds.has(trackId) ? " · locked" : ""}`));
      list.appendChild(row);
    }

    const actions = document.createElement("div");
    actions.className = "actions";
    const preview = document.createElement("button");
    preview.type = "button";
    preview.textContent = "Preview regeneration";
    preview.disabled = busy || candidates.size < 3;
    const selectedCount = document.createElement("span");
    selectedCount.textContent = "Explicit candidate pool: current members selected; add analyzed alternatives if desired.";
    actions.append(preview, selectedCount);

    const results = document.createElement("div");
    results.className = "regeneration-results";
    preview.addEventListener("click", () => previewRegeneration(list, results));
    panel.append(list, actions, results);
    current.appendChild(panel);
    renderRegenerationResults(results);
  }

  function selectedRegenerationCandidates(list) {
    const values = [...list.querySelectorAll("input[type='checkbox']")]
      .filter((input) => input.checked)
      .map((input) => input.value);
    return values.length >= 3 && values.length <= 24 && values.every(validToken) && new Set(values).size === values.length
      ? values
      : null;
  }

  async function previewRegeneration(list, results) {
    if (busy || !activeRevision) return;
    const candidateIds = selectedRegenerationCandidates(list);
    if (!candidateIds) {
      setStatus("Regeneration requires 3–24 unique analyzed candidate tracks.");
      return;
    }
    const lockedIds = activeRevision.sequence.filter((item) => item.locked).map((item) => item.track_id);
    if (lockedIds.some((trackId) => !candidateIds.includes(trackId))) {
      setStatus("Every locked track must remain inside the regeneration candidate pool.");
      return;
    }
    busy = true;
    setStatus("Computing bounded regeneration preview from current evidence…");
    try {
      const response = await originalInvoke("playlist_editor_regeneration_preview", {
        revisionId: activeRevision.revision_id,
        candidateTrackIds: candidateIds,
      });
      if (!validRegenerationPreview(response, activeRevision.revision_id, candidateIds)) {
        throw new Error("Invalid regeneration preview response.");
      }
      regenerationPreview = response;
      regenerationCandidateIds = [...candidateIds];
      renderRegenerationResults(results);
      setStatus(
        response.alternatives.length > 0
          ? "Regeneration preview ready. Choose one path to append as a new immutable revision."
          : "No bounded regeneration path satisfies the current locks and evidence.",
      );
    } catch (_error) {
      regenerationPreview = null;
      regenerationCandidateIds = [];
      results.replaceChildren();
      setStatus("Regeneration preview was rejected safely.");
    } finally {
      busy = false;
    }
  }

  function renderRegenerationResults(results) {
    results.replaceChildren();
    if (!regenerationPreview || !activeRevision) return;
    const heading = document.createElement("h5");
    heading.textContent = `Regeneration ${regenerationPreview.regeneration_id}`;
    results.appendChild(heading);
    for (const alternative of regenerationPreview.alternatives) {
      const card = document.createElement("article");
      card.className = "editor-proposal-choice";
      const title = document.createElement("h5");
      title.textContent = `Regenerated alternative ${alternative.rank}`;
      const sequence = document.createElement("ol");
      for (const step of alternative.sequence) {
        const row = document.createElement("li");
        row.textContent = `${step.display_name}${step.locked ? " · locked" : ""}`;
        sequence.appendChild(row);
      }
      const apply = document.createElement("button");
      apply.type = "button";
      apply.textContent = "Apply as new revision";
      apply.disabled = busy;
      apply.addEventListener("click", () => applyRegeneration(alternative.path_id));
      card.append(title, sequence, apply);
      results.appendChild(card);
    }
  }

  async function applyRegeneration(pathId) {
    if (
      busy ||
      !activeRevision ||
      !regenerationPreview ||
      !validToken(pathId) ||
      regenerationCandidateIds.length < 3
    ) {
      return;
    }
    busy = true;
    setStatus("Replaying regeneration evidence and appending immutable child revision…");
    try {
      const revision = await tauriCore.invoke("playlist_editor_regeneration_apply", {
        revisionId: activeRevision.revision_id,
        candidateTrackIds: regenerationCandidateIds,
        regenerationId: regenerationPreview.regeneration_id,
        pathId,
      });
      if (!validRevision(revision) || revision.operation !== "regenerate") {
        throw new Error("Invalid regenerated revision response.");
      }
    } catch (_error) {
      regenerationPreview = null;
      regenerationCandidateIds = [];
      setStatus("Regeneration apply was rejected safely. Preview again from the current revision.");
      try {
        await refreshHistory();
      } catch (_ignored) {
        // Keep the last trusted view if authoritative history is temporarily unavailable.
      }
    } finally {
      busy = false;
      renderCurrentRevision();
    }
  }

  async function moveTrack(from, to) {
    if (busy || !activeRevision || from === to) {
      return;
    }
    const ordered = activeRevision.sequence.map((item) => item.track_id);
    const [moved] = ordered.splice(from, 1);
    ordered.splice(to, 0, moved);
    await mutate("playlist_editor_reorder", {
      revisionId: activeRevision.revision_id,
      orderedTrackIds: ordered,
    }, "Reorder appended as a new immutable revision.");
  }

  async function changeLock(trackId, shouldLock) {
    if (busy || !activeRevision || !validToken(trackId)) {
      return;
    }
    const locked = new Set(activeRevision.sequence.filter((item) => item.locked).map((item) => item.track_id));
    if (shouldLock) {
      locked.add(trackId);
    } else {
      locked.delete(trackId);
    }
    await mutate("playlist_editor_lock", {
      revisionId: activeRevision.revision_id,
      lockedTrackIds: activeRevision.sequence
        .map((item) => item.track_id)
        .filter((id) => locked.has(id)),
    }, "Lock state appended as a new immutable revision.");
  }

  async function replaceTrack(sourceTrackId, replacementTrackId) {
    if (!validToken(sourceTrackId) || !validToken(replacementTrackId)) {
      setStatus("Choose a valid analyzed replacement track first.");
      return;
    }
    await mutate("playlist_editor_replace", {
      revisionId: activeRevision.revision_id,
      sourceTrackId,
      replacementTrackId,
    }, "Replacement appended as a new immutable revision.");
  }

  async function mutate(command, args, successMessage) {
    if (busy || !activeRevision) {
      return;
    }
    busy = true;
    regenerationPreview = null;
    regenerationCandidateIds = [];
    setStatus("Appending governed playlist revision…");
    try {
      const revision = await originalInvoke(command, args);
      if (!validRevision(revision)) {
        throw new Error("Invalid playlist revision response.");
      }
      activeRevision = revision;
      await refreshReplacementTracks();
      await refreshHistory();
      setStatus(successMessage);
    } catch (_error) {
      setStatus("The edit was rejected safely. Refresh the current revision before retrying.");
      try {
        await refreshHistory();
      } catch (_ignored) {
        // Keep the last trusted local view if authoritative history cannot be refreshed.
      }
    } finally {
      busy = false;
      renderCurrentRevision();
    }
  }

  function renderHistory(history) {
    historyNode.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = `Revision history (${history.revisions.length}${history.history_truncated ? "+" : ""})`;
    const list = document.createElement("ol");
    for (const revision of history.revisions) {
      const item = document.createElement("li");
      item.textContent = `#${revision.revision_index} ${revision.operation} · ${revision.revision_id}`;
      list.appendChild(item);
    }
    historyNode.append(heading, list);
  }

  renderProposalChoices();
  renderCurrentRevision();
})();
