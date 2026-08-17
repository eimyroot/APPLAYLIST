# APPLAYLIST Music Intelligence Roadmap R1–R7

## Status

Proposed product and engineering roadmap derived from Product Architecture v3.

This roadmap supplements the existing Bundle 41–54 release roadmap. It does not erase historical bundle evidence and does not authorize merge, release or deployment.

## Operating rule

The roadmap is vertical and product-first.

Do not broaden APPLAYLIST into a DAW, live DJ engine, streaming service or generic AI suite before the DJ preparation product proves value.

Each release phase must produce a user-visible improvement, measurable acceptance gates and evidence sufficient to stop, continue or change direction.

---

# R1 — Analysis Truth Layer

## Goal

Make APPLAYLIST trustworthy about what it claims to know about a track.

## Product outcome

A DJ can inspect analysis facts, confidence, alternatives, corrections and evidence instead of receiving unexplained scalar values.

## Required capabilities

- robust tempo-family representation,
- beat/downbeat or equivalent timing evidence,
- key/Camelot with alternatives and confidence,
- baseline energy representation,
- loudness/acoustic baseline,
- analysis inspector,
- append-only corrections,
- provider provenance,
- benchmark evidence.

## Existing foundation

Bundles 45–50 already provide the baseline MIR/provider/benchmark and analysis-job evidence path.

## New work

- Music DNA contract implementation,
- consensus-policy foundation,
- richer normalized fact types,
- explicit capability state for unavailable features,
- versioned energy vector foundation.

## Acceptance gates

- no silent provider fallback,
- no path/raw-exception leak,
- confidence/alternatives preserved,
- human correction does not destroy provider evidence,
- deterministic consensus fixtures,
- provider eligibility remains governed.

## Commercial value

Necessary foundation, but not sufficient as the main product moat.

---

# R2 — Transition Intelligence

## Goal

Make APPLAYLIST understand why two musical regions can or cannot work together.

## Product outcome

For a source track/segment, the DJ receives ranked target regions with transition strategy, risks, energy effect and explanation.

## Required capabilities

- segment representation,
- usable mix windows,
- tempo fit,
- phrase fit,
- harmonic fit,
- energy delta,
- basic bass/spectral risk,
- vocal-overlap risk when available,
- transition strategy candidates,
- deterministic context scoring,
- append-only TransitionAssessment persistence,
- structured explanations.

## Initial strategy set

- long blend,
- short blend,
- EQ blend,
- bass swap,
- cut,
- drop swap,
- breakdown transition,
- deliberate contrast.

Other strategies remain capability-gated.

## Acceptance gates

- no universal score without context version,
- hard constraints cannot be outweighed,
- missing evidence stays explicit,
- assessment is reproducible,
- explanation references real evidence,
- no direct provider call from renderer.

## Commercial value

Primary differentiation milestone.

This is the first phase that should be tested with external DJs for willingness-to-pay and repeated workflow use.

---

# R2.5 — Set Intelligence Contract + Runtime

## Goal

Define sequence semantics before introducing path-search complexity.

A set must not be reduced to a chain of locally strong pairwise transitions.

## Product outcome

For a current set state, APPLAYLIST can deterministically produce a bounded Top-N list of eligible next candidates using explicit DJ intent, dramaturgical phase, trajectory, sequence history and persisted TransitionAssessment evidence.

## Canonical contract

`APPLAYLIST_SET_INTELLIGENCE_CONTRACT_V1.md`

## Required capabilities

- `PlaylistIntent`,
- `PlaylistContext`,
- `SetPhase`,
- `SequenceState`,
- required/forbidden/locked-track semantics,
- hard constraints before ranking,
- sequence-level energy/tempo/style/diversity features,
- explicit ranking policy and weights,
- deterministic tie-breaking,
- Top-N `recommend_next`,
- future-feasibility signal with explicit bounded horizon,
- structured sequence-level explanations,
- no hidden fallback to legacy composition.

## Infrastructure rule

The graph is a domain model, not a database mandate.

R2.5 and the first R3 optimizer must not require Neo4j, another graph database or a vector database for correctness.

Transition adjacency may be persisted through existing repository/storage boundaries and indexed by canonical segment/transition IDs.

## Acceptance gates

- intent and context are separate/versioned,
- sequence state is immutable/reconstructable,
- hard constraints cannot be outweighed,
- missing evidence remains explicit,
- identical inputs produce identical Top-N ordering,
- locks/bans/required tracks have deterministic fixtures,
- phase/trajectory behavior has deterministic fixtures,
- ranking never calls MIR providers directly,
- renderer receives no filesystem or sidecar authority,
- a graph DB/vector DB is not required to pass correctness tests.

## Commercial value

This is the semantic bridge that turns Transition Intelligence into a coherent set-building product instead of a pairwise recommendation demo.

---

# R3 — Set Intelligence Graph/Path Optimization

## Goal

Turn Set Intelligence candidate expansion into an intentional set path rather than a sequence of locally good pairs.

## Dependency

R3 starts only after the R2.5 Set Intelligence contract/runtime is proven.

The optimizer consumes Set Intelligence state expansions; it does not define intent, phase, hard-constraint or ranking semantics itself.

## Product outcome

The DJ specifies constraints and desired trajectory; APPLAYLIST proposes an explainable ordered set with alternatives.

## Model

```text
Music DNA nodes
+ segment nodes
+ TransitionAssessment edges
+ PlaylistIntent
+ PlaylistContext
+ SetPhase
+ SequenceState
+ deterministic recommend_next
-> bounded graph/path optimization
```

## First optimizer

Prefer deterministic bounded beam/lookahead search with explicit:

- beam width,
- branching limit,
- lookahead depth,
- maximum expanded states,
- deterministic tie-break policy,
- terminal/search reason,
- policy version.

Do not add a graph database or vector database unless measured requirements later justify one.

## Required capabilities

- eligible-library scope,
- required/forbidden tracks,
- locks,
- target duration,
- tempo policy,
- energy trajectory,
- harmonic-risk policy,
- style constraints,
- novelty/repetition policy,
- bounded graph search/path optimization,
- alternative paths,
- deterministic result under identical inputs,
- explanation of major route decisions.

## Acceptance gates

- path satisfies all hard constraints,
- no hidden mutation of analysis evidence,
- result can be regenerated from recorded inputs,
- alternatives are distinguishable by reason,
- optimizer is bounded for realistic local libraries,
- search-budget exhaustion is not misreported as mathematical infeasibility,
- bounded search beats or meaningfully complements greedy and legacy baselines on named product outcomes.

## Commercial value

Core Pro subscription value.

---

# R4 — Human Editor + Interoperability Release

## Goal

Make the recommendation actually usable in a DJ workflow.

## Product outcome

A DJ can accept, reorder, lock, replace and export the set without surrendering control.

## Required capabilities

- manual reorder,
- lock/unlock,
- replace with alternatives,
- selected transition inspection,
- regeneration around locks,
- playlist revision history,
- M3U8 export,
- JSON evidence export,
- first documented DJ-library adapters,
- path-valid export verification.

## Acceptance gates

- manual edits are preserved,
- export never mutates approved playlist revision,
- deterministic export bytes for identical approved revision/config,
- no proprietary database mutation as default integration strategy,
- clean-machine desktop smoke.

## Commercial value

First realistic paid release candidate.

### Go-to-market checkpoint

Run a bounded pilot with DJs before broadening feature scope.

Measure:

- time from import to usable set,
- percentage of recommendations inspected,
- acceptance/rejection rate,
- manual reorder/replace frequency,
- export completion rate,
- repeat weekly use,
- willingness-to-pay.

---

# R5 — Personal DJ Intelligence

## Goal

Adapt ranking to the artist without rewriting musical truth.

## Product outcome

APPLAYLIST increasingly reflects the DJ's preferred energy curves, transition duration, harmonic risk and style bridges.

## Input signals

- accept/reject,
- replace,
- reorder,
- lock,
- chosen transition strategy,
- moved transition window,
- explicit rating,
- optional imported performance signal with consent.

## Model outputs

- energy-trajectory preference,
- harmonic-risk tolerance,
- tempo-change tolerance,
- preferred blend duration,
- vocal-overlap tolerance,
- style/genre bridge preferences,
- transition-strategy weights,
- novelty/consistency preference.

## Governance

- local-first by default,
- user-resettable,
- versioned,
- explainable influence on ranking,
- measured facts remain immutable,
- no hidden training-data upload.

## Commercial value

Retention and defensibility milestone.

---

# R6 — Advanced Music Intelligence

## Goal

Increase depth only after Transition/Set Intelligence proves product value.

## Candidate capabilities

- richer structure analysis,
- chord timeline,
- semantic embeddings,
- richer style/mood taxonomy,
- stem providers,
- note/pitch transcription,
- audio-to-MIDI,
- higher-quality local GPU modes,
- advanced similarity axes.

## Rule

Every capability must have a named product use-case.

Do not add features solely because a model exists.

## Acceptance gates

- provider governance complete,
- benchmark exists,
- renderer surface stays bounded,
- feature demonstrably improves a decision or workflow,
- cost/performance is measured.

## Commercial value

Studio-tier differentiation and future SDK assets.

---

# R7 — Producer Intelligence + B2B Intelligence Layer

## Goal

Reuse the same governed Music DNA and decision system outside DJ preparation.

## Producer vertical candidates

- arrangement diagnostics,
- energy/tension progression,
- mix balance/reference comparison,
- loudness/dynamics diagnostics,
- spectral masking guidance,
- stereo/mono compatibility,
- structure comparison,
- chord/tonal inspection,
- stem/note-assisted workflows.

## B2B candidates

- Transition Intelligence SDK,
- Music DNA API/SDK,
- recommendation/explanation components,
- library intelligence for third-party DJ tools,
- offline/on-device analysis packages.

## Entry gate

Do not begin broad B2B or producer expansion until the DJ product has evidence of repeated value and a stable versioned intelligence contract.

---

# Suggested business model checkpoints

## Pilot

Audience:

- working/open-format/club DJs,
- DJs with large local libraries,
- DJs who already use Rekordbox/Traktor/Serato/djay workflows.

Offer:

- bounded beta,
- local-first analysis,
- transition/set preparation,
- no forced library migration.

Primary question:

Does the product save preparation time and surface transition options the DJ would actually use?

## Paid DJ tier

Candidate value bundle:

- unlimited local library,
- full analysis inspector,
- Transition Intelligence,
- Explainable Set Builder,
- advanced export/interoperability,
- personal preference model when mature.

Pricing must be validated in pilot rather than frozen by architecture.

## Studio tier

Candidate later value bundle:

- advanced semantic models,
- stems/transcription,
- producer diagnostics,
- quality/GPU analysis modes,
- larger batch workflows.

## Optional compute

Cloud or expensive GPU capabilities, if introduced, should be separate and transparent rather than making basic local analysis depend on variable per-request cost.

---

# Time model

Calendar estimates are planning ranges, not promises.

Assuming one focused implementation stream and no major architecture reversal:

| Phase | Planning range | Exit condition |
|---|---:|---|
| R1 | 4–6 focused engineering weeks | Music DNA truth layer is reliable and inspectable |
| R2 | 4–7 weeks | transition recommendations are explainable and testable with DJs |
| R2.5 | focused contract/runtime slice | sequence semantics and deterministic Top-N candidate expansion are proven |
| R3 | 4–6 weeks | bounded graph set builder satisfies constraints and trajectories |
| R4 | 3–5 weeks | end-to-end editable/exportable paid-release candidate |
| R5 | 4–8 weeks | preference learning measurably improves user ranking |
| R6 | incremental | advanced capabilities prove named product value |
| R7 | after market evidence | producer/B2B expansion has a validated entry case |

These ranges exclude unbounded model research, external licensing negotiations and large cross-platform integration surprises.

---

# Decision metrics

Engineering metrics alone are insufficient.

Track product metrics from R2 onward:

- analysis completion/failure rate,
- transition recommendation acceptance,
- transition recommendation inspection rate,
- replacement/reorder rate,
- set completion rate,
- export completion rate,
- median preparation-time change,
- repeat use,
- user-reported trust/explainability,
- paid conversion,
- retention,
- optional compute cost per active user if introduced.

# Stop / pivot conditions

Reconsider scope if:

- Transition Intelligence does not beat simpler BPM/key/energy heuristics in blinded human review,
- explanations do not increase user trust or decision speed,
- graph optimization creates technically valid but musically unusable sets,
- interoperability friction dominates the workflow,
- provider licensing makes the chosen production path economically unsustainable,
- users primarily want a different problem solved.

# Current next step

1. Keep Bundle 51 Music DNA + Transition Intelligence runtime PR #112 as the dependency boundary until separately authorized for merge.
2. Define and verify `APPLAYLIST_SET_INTELLIGENCE_CONTRACT_V1.md` as a stacked contract slice.
3. Implement the minimum Set Intelligence runtime: intent/context/phase/state, hard gates, deterministic ranking and Top-N `recommend_next`.
4. Only then implement bounded graph/path optimization.

Do not start graph/vector database adoption, stems, producer features or broad semantic-model integration before these contracts and runtime gates are proven.
