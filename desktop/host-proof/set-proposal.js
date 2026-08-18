(() => {
  "use strict";

  const invoke = window.__TAURI__?.core?.invoke;
  const section = document.getElementById("set-proposal");
  const refreshButton = document.getElementById("set-proposal-refresh");
  const trackList = document.getElementById("set-proposal-track-list");
  const emptyState = document.getElementById("set-proposal-empty");
  const seedSelect = document.getElementById("set-proposal-seed");
  const targetInput = document.getElementById("set-proposal-target");
  const generateButton = document.getElementById("set-proposal-generate");
  const status = document.getElementById("set-proposal-status");
  const results = document.getElementById("set-proposal-results");

  if (
    !section ||
    !refreshButton ||
    !trackList ||
    !emptyState ||
    !seedSelect ||
    !targetInput ||
    !generateButton ||
    !status ||
    !results
  ) {
    return;
  }

  const STATUS_VALUES = new Set([
    "target_reached",
    "paths_found",
    "no_eligible_path",
    "not_proven_missing_evidence",
    "budget_exhausted",
  ]);
  const TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,255}$/;
  const selectedTrackIds = new Set();
  let analyzedTracks = new Map();
  let busy = false;

  function exactKeys(value, keys) {
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return false;
    }
    const actual = Object.keys(value).sort();
    const expected = [...keys].sort();
    return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
  }

  function validTrackId(value) {
    return (
      typeof value === "string" &&
      value.length > 0 &&
      value.length <= 256 &&
      value.trim() === value &&
      !value.includes("/") &&
      !value.includes("\\") &&
      !/[\u0000-\u001f\u007f]/.test(value)
    );
  }

  function pathShapedText(value) {
    return value.startsWith("/") || value.startsWith("\\\\") || /^[A-Za-z]:[\\/]/.test(value);
  }

  function validDisplayName(value) {
    return (
      typeof value === "string" &&
      value.length > 0 &&
      value.length <= 512 &&
      value.trim() === value &&
      !/[\u0000-\u001f\u007f]/.test(value) &&
      !pathShapedText(value)
    );
  }

  function validToken(value, maximum = 256) {
    return typeof value === "string" && value.length <= maximum && TOKEN.test(value);
  }

  function validUnitNumber(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
  }

  function validCodes(values) {
    return Array.isArray(values) && values.length <= 128 && values.every((value) => validToken(value, 128));
  }

  function validObjective(value, expectedDepth) {
    return (
      exactKeys(value, [
        "depth",
        "mean_candidate_score",
        "minimum_candidate_score",
        "required_track_completion",
        "remaining_required_count",
        "target_reached",
      ]) &&
      Number.isInteger(value.depth) &&
      value.depth === expectedDepth &&
      validUnitNumber(value.mean_candidate_score) &&
      validUnitNumber(value.minimum_candidate_score) &&
      validUnitNumber(value.required_track_completion) &&
      Number.isInteger(value.remaining_required_count) &&
      value.remaining_required_count >= 0 &&
      value.remaining_required_count <= 24 &&
      typeof value.target_reached === "boolean"
    );
  }

  function validAlternative(value, expectedRank) {
    if (
      !exactKeys(value, [
        "path_id",
        "rank",
        "sequence",
        "transition_ids",
        "candidate_scores",
        "objective",
        "explanation_codes",
      ]) ||
      !validToken(value.path_id) ||
      value.rank !== expectedRank ||
      !Array.isArray(value.sequence) ||
      value.sequence.length < 2 ||
      value.sequence.length > 8 ||
      !Array.isArray(value.transition_ids) ||
      !Array.isArray(value.candidate_scores) ||
      value.transition_ids.length !== value.candidate_scores.length ||
      value.sequence.length !== value.candidate_scores.length + 1 ||
      !validCodes(value.explanation_codes)
    ) {
      return false;
    }

    for (let index = 0; index < value.sequence.length; index += 1) {
      const step = value.sequence[index];
      if (
        !exactKeys(step, ["order_index", "track_id", "display_name", "phase_id"]) ||
        step.order_index !== index ||
        !validTrackId(step.track_id) ||
        !validDisplayName(step.display_name) ||
        !validToken(step.phase_id)
      ) {
        return false;
      }
    }
    if (!value.transition_ids.every((item) => validToken(item))) {
      return false;
    }
    if (!value.candidate_scores.every(validUnitNumber)) {
      return false;
    }
    return validObjective(value.objective, value.candidate_scores.length);
  }

  function validProposal(value) {
    if (
      !exactKeys(value, [
        "schema",
        "proposal_id",
        "status",
        "alternatives",
        "reason_codes",
        "warning_codes",
        "budget_exhausted",
        "missing_evidence_detected",
        "deterministic_ordering",
        "activation_authorized",
        "personal_dj_model_training_authorized",
      ]) ||
      value.schema !== "applaylist-desktop-set-proposal-r1" ||
      !validToken(value.proposal_id) ||
      !STATUS_VALUES.has(value.status) ||
      !Array.isArray(value.alternatives) ||
      value.alternatives.length > 3 ||
      !value.alternatives.every((item, index) => validAlternative(item, index + 1)) ||
      !validCodes(value.reason_codes) ||
      !validCodes(value.warning_codes) ||
      typeof value.budget_exhausted !== "boolean" ||
      typeof value.missing_evidence_detected !== "boolean" ||
      value.deterministic_ordering !== true ||
      value.activation_authorized !== false ||
      value.personal_dj_model_training_authorized !== false
    ) {
      return false;
    }
    if (["target_reached", "paths_found"].includes(value.status) && value.alternatives.length === 0) {
      return false;
    }
    if (value.status === "no_eligible_path" && value.alternatives.length !== 0) {
      return false;
    }
    return true;
  }

  function validInspectorTrack(value) {
    return (
      value !== null &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      validTrackId(value.track_id) &&
      typeof value.title === "string" &&
      value.title.trim().length > 0 &&
      value.title.length <= 512 &&
      !pathShapedText(value.title) &&
      (value.artist === null ||
        (typeof value.artist === "string" &&
          value.artist.length > 0 &&
          value.artist.length <= 512 &&
          !pathShapedText(value.artist))) &&
      value.status === "succeeded"
    );
  }

  function labelForTrack(track) {
    return track.artist ? `${track.artist} — ${track.title}` : track.title;
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function updateControls() {
    const selected = [...selectedTrackIds].filter((trackId) => analyzedTracks.has(trackId)).sort();
    const previousSeed = seedSelect.value;
    seedSelect.replaceChildren();
    for (const trackId of selected) {
      const track = analyzedTracks.get(trackId);
      const option = document.createElement("option");
      option.value = trackId;
      option.textContent = labelForTrack(track);
      seedSelect.appendChild(option);
    }
    if (selected.includes(previousSeed)) {
      seedSelect.value = previousSeed;
    }

    const maximumTarget = Math.min(8, selected.length);
    targetInput.max = String(Math.max(3, maximumTarget));
    if (Number(targetInput.value) > maximumTarget) {
      targetInput.value = maximumTarget >= 3 ? String(maximumTarget) : "3";
    }
    seedSelect.disabled = busy || selected.length === 0;
    targetInput.disabled = busy || selected.length < 3;
    refreshButton.disabled = busy;
    generateButton.disabled = busy || selected.length < 3 || typeof invoke !== "function";
  }

  function renderTrackSelection(items) {
    analyzedTracks = new Map(
      items
        .filter(validInspectorTrack)
        .map((track) => [track.track_id, { track_id: track.track_id, title: track.title, artist: track.artist }]),
    );
    selectedTrackIds.clear();
    trackList.replaceChildren();

    const tracks = [...analyzedTracks.values()].sort((left, right) =>
      labelForTrack(left).localeCompare(labelForTrack(right)),
    );
    emptyState.hidden = tracks.length !== 0;

    for (const track of tracks) {
      const item = document.createElement("li");
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          selectedTrackIds.add(track.track_id);
        } else {
          selectedTrackIds.delete(track.track_id);
        }
        updateControls();
      });
      const text = document.createElement("span");
      text.textContent = labelForTrack(track);
      label.append(checkbox, text);
      item.appendChild(label);
      trackList.appendChild(item);
    }
    updateControls();
  }

  function appendCodes(container, headingText, codes) {
    if (codes.length === 0) {
      return;
    }
    const heading = document.createElement("h5");
    heading.textContent = headingText;
    const list = document.createElement("ul");
    for (const code of codes) {
      const item = document.createElement("li");
      item.textContent = code;
      list.appendChild(item);
    }
    container.append(heading, list);
  }

  function renderProposal(proposal) {
    results.replaceChildren();

    const summary = document.createElement("div");
    summary.className = "proposal-summary";
    const title = document.createElement("h3");
    title.textContent = `Proposal ${proposal.proposal_id}`;
    const state = document.createElement("p");
    state.textContent = `Status: ${proposal.status}`;
    summary.append(title, state);
    appendCodes(summary, "Reasons", proposal.reason_codes);
    appendCodes(summary, "Warnings", proposal.warning_codes);
    results.appendChild(summary);

    if (proposal.alternatives.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No eligible bounded proposal was found for this scope.";
      results.appendChild(empty);
      return;
    }

    for (const alternative of proposal.alternatives) {
      const card = document.createElement("article");
      card.className = "proposal-alternative";
      const heading = document.createElement("h4");
      heading.textContent = `Alternative ${alternative.rank}`;
      const metrics = document.createElement("p");
      metrics.textContent =
        `Mean ${alternative.objective.mean_candidate_score.toFixed(3)} · ` +
        `Minimum ${alternative.objective.minimum_candidate_score.toFixed(3)} · ` +
        `Target ${alternative.objective.target_reached ? "reached" : "partial"}`;

      const ordered = document.createElement("ol");
      for (let index = 0; index < alternative.sequence.length; index += 1) {
        const step = alternative.sequence[index];
        const item = document.createElement("li");
        const score =
          index === 0 ? "seed" : `score ${alternative.candidate_scores[index - 1].toFixed(3)}`;
        item.textContent = `${step.display_name} — ${score}`;
        ordered.appendChild(item);
      }
      card.append(heading, metrics, ordered);
      appendCodes(card, "Path explanation", alternative.explanation_codes);
      results.appendChild(card);
    }
  }

  async function refreshAnalyzedTracks() {
    if (busy || typeof invoke !== "function") {
      return;
    }
    busy = true;
    updateControls();
    setStatus("Loading analyzed tracks…");
    try {
      const response = await invoke("analysis_inspector_list", { filter: "all" });
      if (
        response === null ||
        typeof response !== "object" ||
        response.filter !== "all" ||
        !Array.isArray(response.items)
      ) {
        throw new Error("Invalid analysis inspector response.");
      }
      renderTrackSelection(response.items);
      setStatus(
        analyzedTracks.size >= 3
          ? "Select 3–24 analyzed tracks, choose a seed, then generate a proposal."
          : "At least three successful analyzed tracks are required.",
      );
    } catch (_error) {
      analyzedTracks = new Map();
      selectedTrackIds.clear();
      trackList.replaceChildren();
      emptyState.hidden = false;
      setStatus("Analyzed tracks could not be loaded safely.");
    } finally {
      busy = false;
      updateControls();
    }
  }

  async function generateProposal() {
    if (busy || typeof invoke !== "function") {
      return;
    }
    const trackIds = [...selectedTrackIds].sort();
    const seedTrackId = seedSelect.value;
    const targetTrackCount = Number(targetInput.value);
    if (
      trackIds.length < 3 ||
      trackIds.length > 24 ||
      !trackIds.every(validTrackId) ||
      !trackIds.includes(seedTrackId) ||
      !Number.isInteger(targetTrackCount) ||
      targetTrackCount < 3 ||
      targetTrackCount > 8 ||
      targetTrackCount > trackIds.length
    ) {
      setStatus("Select a valid bounded proposal scope first.");
      return;
    }

    busy = true;
    updateControls();
    results.replaceChildren();
    setStatus("Generating read-only set proposal…");
    try {
      const proposal = await invoke("set_proposal_generate", {
        trackIds,
        seedTrackId,
        targetTrackCount,
      });
      if (!validProposal(proposal)) {
        throw new Error("Invalid set proposal response.");
      }
      renderProposal(proposal);
      setStatus("Set proposal generated from persisted analysis evidence.");
    } catch (_error) {
      setStatus("The set proposal could not be generated safely.");
    } finally {
      busy = false;
      updateControls();
    }
  }

  refreshButton.addEventListener("click", refreshAnalyzedTracks);
  generateButton.addEventListener("click", generateProposal);
  targetInput.addEventListener("change", updateControls);
  updateControls();
})();
