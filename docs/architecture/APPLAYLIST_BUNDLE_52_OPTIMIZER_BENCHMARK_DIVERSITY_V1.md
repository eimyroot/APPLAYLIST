# APPLAYLIST Bundle 52 — Optimizer Benchmark + Alternative Diversity V1

Status: implementation candidate

## Purpose

This slice evaluates the canonical bounded beam/lookahead optimizer without changing its musical authority boundaries or silently activating a new production policy.

It adds two governed layers:

1. an evidence-only greedy-vs-beam benchmark harness,
2. deterministic post-search alternative-path diversity selection.

The benchmark answers whether bounded search provides measurable sequence-level value over a strict greedy `recommend_next` baseline on the same evidence.

The diversity layer answers whether the Top-K alternatives presented to a DJ are materially different paths rather than cosmetic near-duplicates.

Neither layer changes `TransitionAssessment`, Set Intelligence scoring, hard gates, Music DNA, provider analysis, persistence semantics, release state or deployment state.

## Canonical dependency

This slice starts from canonical Bundle 52 optimizer v1 after PR #117:

`be8515975a5befa1b2b4d860c952758debd7ad22`

## Authority boundaries

```text
MusicDNARevision
    ↓
TransitionAssessment              pairwise musical evidence authority
    ↓
recommend_next                    candidate hard-gate + Set Intelligence ranking authority
    ↓
optimize_set_lookahead            bounded sequence-search authority
    ↓
raw SetOptimizerResult
    ├── benchmark metrics         evidence only
    └── diversity selection       presentation/alternative-set evidence only
```

The benchmark does not create a new scoring function.

The diversity selector does not reorder rank #1, recalculate a path objective or change candidate scores. It only determines which lower-ranked raw alternatives are sufficiently different to be useful as separate options.

## Strict greedy baseline

The benchmark derives the greedy baseline from the beam policy family while fixing:

```text
beam_width = 1
per_state_candidate_limit = 1
alternative_limit = 1
```

The same maximum depth and global expansion-budget family are retained.

This means greedy is exactly:

> follow the current Top-1 `recommend_next` candidate at each depth.

It is not a second handcrafted baseline with different music semantics.

## Beam benchmark

The supplied canonical `SetOptimizerPolicy` is run unchanged.

Greedy and beam receive identical:

- `PlaylistIntent`,
- `PlaylistContext`,
- `SequenceState`,
- base `TransitionContext`,
- persisted `TransitionAssessment` adjacency,
- Set Intelligence ranking policy,
- duration evidence,
- style metadata,
- critical-warning metadata,
- generated provenance timestamp.

Both strategies are executed twice using identical normalized inputs. The benchmark records whether exact dataclass equality is reproduced on replay.

A replay mismatch is evidence of a determinism defect; the benchmark does not hide it.

## Benchmark metrics

V1 records, per strategy:

- optimizer identity/version,
- result status,
- whether the best path reaches the requested set target,
- best required-track completion,
- best mean candidate score,
- best minimum candidate score,
- deepest search depth,
- expanded candidate count,
- beam-pruned candidate count,
- budget exhaustion,
- missing-evidence detection,
- returned alternative count,
- deterministic replay equality.

Comparison-level evidence records:

- whether beam reaches a target that greedy misses,
- required-track completion delta,
- expanded-candidate delta,
- number of alternatives rejected as near-duplicates,
- explicit `activation_authorized=false`.

No universal benchmark winner score exists in v1.

## Alternative-path diversity

The canonical optimizer may legitimately return paths that are close in sequence space. Raw Top-K ranking remains useful evidence, but presenting several nearly identical paths as independent choices creates false option diversity.

V1 therefore adds a separate `AlternativeDiversityPolicy`.

Policy dimensions:

```text
alternative_limit
max_track_jaccard
max_shared_prefix_fraction
minimum_differing_positions
allow_similarity_fallback
```

### Track Jaccard

For added track identities:

```text
J(A,B) = |tracks(A) ∩ tracks(B)| / |tracks(A) ∪ tracks(B)|
```

It detects alternatives that contain mostly the same tracks even if their order differs.

### Shared-prefix fraction

```text
shared_prefix_length / min(path_length_A, path_length_B)
```

It detects alternatives that make the same early decisions and diverge only near the end.

Early divergence matters because alternative plans should provide the DJ with genuinely different next choices, not merely different tails several transitions later.

### Differing positions

The policy counts positional differences plus path-length differences.

This prevents an alternative identical at every compared position from passing solely because another similarity measure happens to remain below a configured threshold.

## Selection semantics

1. Raw source alternatives are processed in authoritative source-rank order.
2. Source rank #1 is always preserved.
3. Each subsequent path is compared against **every** already selected path.
4. A violation against any selected path rejects the candidate under strict mode.
5. Accepted paths retain their original evidence and are reranked contiguously only inside the derived `SetAlternativeSelection` view.
6. The original `SetOptimizerResult` remains immutable and untouched.

The decision evidence records:

- source path ID/rank,
- selected/rejected state,
- binding selected path,
- Jaccard overlap,
- shared-prefix fraction,
- differing positions,
- explicit reason codes.

## Similarity fallback

`allow_similarity_fallback=false` is the normal governed mode.

If strict diversity produces fewer alternatives than requested, that shortage is truthful evidence. The system does not invent alternatives.

If a caller explicitly enables `allow_similarity_fallback=true`, rejected source-ranked paths may be used to fill the requested limit. Each such decision is marked:

`similarity_fallback_selected`

and the selection sets:

`similarity_fallback_used=true`

This prevents a fallback from masquerading as strict diversity success.

## Determinism

Diversity selection is pure and deterministic over:

- immutable raw optimizer result,
- explicit diversity policy.

Selection identity uses canonical sorted JSON and SHA-256.

Stable path identity is used as the final tie boundary.

No wall-clock time, random seed, hash iteration order, external service or LLM is used.

## Benchmark truth boundary

A benchmark case is evidence, not activation authority.

`OptimizerBenchmarkComparison.activation_authorized` is structurally required to remain `false` in V1. Construction with `true` fails closed.

A later production-policy decision requires a separate governed acceptance slice using a representative scenario corpus and explicit acceptance thresholds.

## Required representative benchmark corpus before activation

The harness is now capable of deterministic scenario evaluation, but production activation should wait for a versioned corpus covering at least:

1. greedy locally attractive / future dead-end scenarios,
2. required-track reachability,
3. multi-phase context transitions,
4. energy trajectory changes,
5. locked-position obligations,
6. forbidden/repeat hard gates,
7. missing duration evidence,
8. bounded-budget truncation,
9. high-branching adjacency,
10. alternative near-duplicate pressure.

Corpus provenance must identify how each scenario was constructed and which evidence is synthetic versus derived from real analyzed music.

## Acceptance questions for the later benchmark-corpus gate

Do not reduce these to one universal score.

Evaluate separately:

- Does beam reduce target failures versus greedy?
- Does beam improve required-track completion?
- Does it introduce any hard-constraint regressions? Expected answer: zero.
- Does bounded search remain deterministic under fixed expansion budgets?
- What is the expansion/runtime cost increase?
- How often does diversity filtering remove nominal Top-K alternatives?
- Does strict diversity frequently leave fewer alternatives than requested?
- Are the remaining alternatives useful to a human DJ?
- Does any improvement persist across different set intents/phases?

## Out of scope

- benchmark-based production activation,
- automatic optimizer-policy switching,
- Personal DJ Model influence,
- preference learning from selected alternatives,
- renderer/Tauri integration,
- graph/vector database adoption,
- LLM planning authority,
- first-track seeding,
- release/signing/notarization,
- deployment.

## Next governed boundary

After this slice is green, the next correct work is **representative benchmark-corpus R1 + acceptance thresholds**, not Personal DJ Model activation.

Only after measured optimizer behavior is accepted should the product persist/visualize final `SetPlanRevision` choices and later use explicit DJ corrections as Personal DJ Model evidence.
