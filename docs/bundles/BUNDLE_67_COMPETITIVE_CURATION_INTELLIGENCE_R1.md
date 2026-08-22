# Bundle 67 — Competitive Curation Intelligence R1

## Product position

APPLAYLIST should not become another performance deck.

The mature DJ products already have strong positions there:

- rekordbox: library/performance workflow plus BPM/grid/key/phrase/vocal analysis, intelligent playlists and personalized cue preparation;
- Traktor: mature live performance, flexible beatgrids, stems, effects and hardware workflows;
- Serato: mature live performance, stems, hardware ecosystem, crates and preparation workflow;
- DJ.Studio: offline harmonic/BPM ordering, transition presets/timeline editing and bridge-style solving;
- Mixed In Key: key/BPM/energy/cue preparation;
- Lexicon / Engine DJ: cross-library organization and rule-driven smart lists.

APPLAYLIST's defensible target is different:

> **Explainable local-first DJ set curation intelligence that understands intent, whole-set dramaturgy, transition feasibility, meaningful alternatives, and the DJ's own evidence-backed preferences.**

This slice builds the first shadow scoring layer for that target.

## Why the current canonical engine is not enough

Canonical Set Intelligence already has strong foundations:

- immutable `TransitionAssessment` evidence;
- bounded optimizer search;
- `PlaylistIntent` and set phases;
- energy trajectories;
- locks and regeneration;
- deterministic alternatives;
- human review and pilot evidence;
- meaningful-diversity/style-energy post-search gates.

But the current ranking path still leaves valuable existing MusicDNA evidence underused at whole-set level. In particular, phrase boundaries, structural segments, percussive ratio, harmonic ratio and beat stability are not yet a combined curation signal. Style evidence is also commonly a flat genre string.

That gap matches the R4 human finding: individually plausible tracks can still form a weak DJ segment because the set drifts, saturates one subgenre, loses energy, or produces alternatives with no meaningful musical difference.

## R1 architecture

### 1. TrackCurationEvidence

A versioned bounded projection of already-existing evidence:

- style tags and deterministic parent families;
- baseline energy;
- percussive ratio;
- harmonic ratio;
- beat stability;
- phrase-boundary density;
- structural-label diversity;
- optional explicit vocal presence;
- analysis revision and evidence refs.

`vocal_presence` is never inferred from unrelated fields. If no explicit vocal evidence exists, it remains unavailable.

### 2. CompetitiveCurationPolicy

R1 evaluates whole paths across:

- style target fit;
- adjacent style continuity;
- energy trajectory fit;
- texture/groove continuity;
- phrase/structure readiness;
- unexplained contrast control;
- non-target style saturation control;
- evidence completeness.

The policy is deterministic and versioned.

### 3. Goal-aware contrast

Variation is not automatically bad.

A deliberate contrast transition is not counted as unexplained drift. `STYLE_BRIDGE` goals reduce the weight of raw continuity/contrast penalties. This lets the system distinguish creative dramaturgy from accidental genre jumps instead of forcing every set into stylistic sameness.

### 4. Shadow-only authority

R1 cannot:

- rewrite optimizer rank;
- rewrite candidate scores;
- mutate `TransitionAssessment`;
- activate a new optimizer policy;
- authorize release/deploy/production;
- train a personal DJ model.

It compares source optimizer paths and produces an independent shadow preference only.

## Competitive benchmark fixture

`tests/fixtures/competitive_curation_r1.json` captures five bounded regression scenarios derived from the R4 qualitative selection review:

1. coherent House / Tech House peak progression;
2. excessive UKG concentration;
3. sudden rave-techno drift;
4. under-energy peak path;
5. near-equivalent alternatives that should not create a fake winner.

The fixture is regression evidence, not fabricated human scoring and not production truth.

## Competitive roadmap after R1

### R2 — Human preference calibration

Bind genuine blinded-review and qualitative DJ findings to curation reason codes. Measure whether shadow preference agrees with actual DJ preference before activation.

Target activation evidence should include:

- all required set roles;
- genuine pairwise human judgments;
- explicit tie/abstain handling;
- drift/energy failure labels;
- confidence and disagreement reporting;
- no fabricated ratings.

### R3 — Phrase + vocal transition intelligence

Add explicit measured vocal-presence / vocal-region evidence and improve phrase/section transition windows. Do not infer vocals from unrelated acoustic ratios.

### R4 — Meaningful alternative generator / bridge solver

Do not merely reject weak A/B alternatives. Generate bounded alternatives with a minimum musical-distance target and search the local library for bridge tracks when a transition or dramaturgical gap cannot be solved inside the current candidate pool.

### R5 — DJ preference memory, local first

Learn bounded personal preferences from accepted/rejected/reordered/replaced/locked choices and blinded human review. Preference evidence must remain inspectable, reversible, versioned and local by default.

### R6 — Cross-software preparation output

Export useful preparation evidence back into the DJ's existing performance ecosystem rather than replacing it:

- ordered playlists;
- cue/mix-window suggestions when supported and verified;
- explanation notes;
- alternative next-track groups;
- adapters for rekordbox / Traktor / Serato-compatible workflows where technically and legally feasible.

### R7 — Explainable Set Map UX

A DJ-facing view should answer:

- why this track is here;
- why this transition works or is risky;
- where energy/style/texture is drifting;
- what three meaningfully different next choices exist;
- what changes if a track is locked/rejected;
- which evidence is measured, derived, missing or uncertain.

## Activation principle

`SHADOW_SCORE != OPTIMIZER_AUTHORITY`

No ranking activation is justified merely because R1 tests are green. The shadow model must first demonstrate material agreement with genuine DJ evidence and outperform the current source ranking on bounded pilot cases without introducing unacceptable false positives or collapsing creative diversity.

## Security / privacy

R1 is pure in-memory intelligence over supplied evidence:

- no audio file reads;
- no MIR/provider execution;
- no network calls;
- no cloud upload;
- no hidden telemetry;
- no persistence side effects.

## Authority

- `RELEASE_AUTHORIZATION=NO`
- `DEPLOY_AUTHORIZATION=NO`
- `PRODUCTION_ACTIVATION=NO`
- `OPTIMIZER_RANKING_ACTIVATION=NO`
- `PDM_TRAINING=NO`
- `MERGE_AUTHORIZATION=NO` until separate explicit `MERGE GO`
