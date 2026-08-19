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
  const OPERATIONS = new Set(["accept", "reorder", "lock", "replace"]);
  let lastProposal = null;
  let activeRevision = null;
  let replacementTracks = new Map();
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
