# Bundle 65 — Meaningful Diversity + Style/Energy Coherence R1

## Status

Implementation slice for Issue #151. Evidence-only. No merge, release, deploy, production activation, optimizer-ranking activation, or Personal DJ Model training is authorized by this bundle.

## Pilot provenance

R4 Pilot Run 1 produced a real qualitative DJ finding:

- technically different greedy/beam paths can be musically almost indistinguishable;
- some selections drift too far into UKG / UK bassline concentration;
- some cases jump abruptly into rave techno;
- some role selections, especially peak-time, can lack sufficient energy;
- individually plausible tracks do not guarantee coherent set-level sequencing.

This bundle does not fabricate numeric human ratings from that qualitative review. It implements deterministic machinery that can test these findings in future governed runs.

## Root-cause finding

The existing real-library pilot path used `Set Intelligence`, but the pilot materializer did not pass `style_tags_by_track`, and its `SetPhase` carried no `style_targets` / `style_avoid`. Therefore the style-fit capability present in `set_engine.py` was not active for that pilot. The pilot energy trajectory also used a broad tolerance of `0.35`.

This bundle deliberately does **not** mutate the historical optimizer result or silently retune source ranking. It adds a post-search evidence gate for meaningful musical diversity and coherence.

## Architecture

Invariant:

`TECHNICALLY_DIFFERENT != MUSICALLY_MEANINGFUL_DIFFERENCE`

The existing bounded-beam / Set Intelligence search remains the only path-search and source-ranking authority.

New components:

- `core/intelligence/meaningful_diversity_contract.py`
  - bounded, immutable evidence contracts;
  - explicit statuses: `sufficient`, `insufficient_meaningful_diversity`, `not_proven_missing_evidence`;
  - style/energy coherence evidence;
  - pairwise meaningful-distance evidence;
  - activation structurally forbidden.

- `services/intelligence/meaningful_diversity.py`
  - deterministic path coherence assessment;
  - adjacent style-drift detection;
  - style-target / style-avoid assessment;
  - non-target style saturation detection;
  - energy trajectory / phase coherence;
  - cross-strategy greedy-vs-beam meaningful comparison;
  - source rank #1 preserved for same-result alternative selection.

- `services/intelligence/real_library_meaningful_review.py`
  - versioned wrapper around the existing real-library materializer;
  - historical R1/R2 evidence is not modified;
  - library genre metadata is explicit style evidence with provenance;
  - provider-derived canonical energy remains the energy evidence;
  - non-RESET roles use the explicitly selected seed track genre as a review-only style anchor;
  - RESET remains a style-bridge role and therefore does not receive a seed-genre hard anchor;
  - review-only energy tolerance is `0.15`; this does not feed back into optimizer ranking;
  - reviewer packet is withheld unless every case passes the meaningful gate;
  - failed runs may emit the private gate report only, never a reviewer packet.

## Meaningful distance

Two paths must first be technically different. Musical distance then combines position-aligned:

- style distance;
- energy distance.

Default weights:

- style `0.60`;
- energy `0.40`.

Default minimum meaningful distance: `0.20`.

Missing required style or energy evidence is never interpreted as positive diversity.

## Coherence gates

Default R1 checks include:

- minimum style coherence `0.55`;
- minimum energy coherence `0.70`;
- minimum adjacent style overlap `0.20`;
- maximum style-drift fraction `0.25`;
- maximum avoided-style fraction `0.0`;
- maximum non-target style concentration `0.60`;
- complete style evidence required;
- complete energy evidence required.

The initial CI run proved the earlier `0.55` energy floor and `0.35` drift fraction were too permissive for the explicit peak-energy and abrupt-drift negative fixtures. R1 therefore tightens those two evidence gates to `0.70` and `0.25`; this changes only post-search evidence acceptance and never source optimizer ranking.

These values are versioned policy, not trained truth. Human pilot evidence may justify later policy changes in a separate governed slice.

## Security / privacy

- no network calls;
- no analytics SaaS;
- no cloud audio upload;
- no private local paths added to reviewer output by this bundle;
- bounded style-tag cardinality and string length;
- duplicate per-track musical evidence rejected;
- evidence artifacts refuse overwrite in the new gated wrapper;
- failed gate withholds blinded reviewer packet;
- no optimizer score, rank, TransitionAssessment, or historical evidence mutation.

## Test matrix

Unit and integration tests cover:

1. technically different but musically near-equivalent paths are rejected;
2. meaningfully different coherent alternatives can pass;
3. style drift is surfaced;
4. avoided style is surfaced;
5. non-target style saturation is surfaced;
6. peak/role energy mismatch is surfaced;
7. missing style/energy evidence returns `NOT_PROVEN_MISSING_EVIDENCE`;
8. deterministic replay with reordered evidence input;
9. duplicate evidence rejection;
10. bounded untrusted style-tag cardinality;
11. cross-strategy greedy-vs-beam comparison;
12. failed real-library gate writes a report but withholds reviewer/private reviewer artifacts;
13. source path ranks and identities remain unchanged.

## Independent verification requirements

Before merge authorization:

- CI must pass on supported Python versions;
- PR Guard must pass;
- changed-file diff must match Issue #151 scope;
- no unresolved review threads;
- independent inspection must confirm no activation authority and no source-rank mutation;
- no PASS may be asserted solely from code review without executed gates.

## Authority

- `RELEASE_AUTHORIZATION=NO`
- `DEPLOY_AUTHORIZATION=NO`
- `PRODUCTION_ACTIVATION=NO`
- `OPTIMIZER_RANKING_ACTIVATION=NO`
- `PDM_TRAINING=NO`
- `MERGE_AUTHORIZATION=NO` until separate explicit `MERGE GO`
