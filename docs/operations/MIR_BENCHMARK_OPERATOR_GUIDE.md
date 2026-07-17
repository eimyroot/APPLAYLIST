# APPLAYLIST MIR Benchmark Operator Guide

## Purpose

Run reproducible local quality evaluation against audio and annotations stored outside the repository. This command never downloads datasets, uploads audio, writes production databases or changes the production provider.

## Schema Tree

```text
external dataset root
├── audio files
└── manifest JSON
    └── load_dataset_manifest
        ├── schema/version validation
        ├── dataset/license/checksum evidence
        ├── unique item IDs and paths
        ├── root containment
        └── BenchmarkItem[]
            └── MIRBenchmarkRunner
                ├── revalidate source containment
                ├── RoutedAnalysisService
                ├── BPM/key/energy/runtime evidence
                ├── controlled failure rows
                ├── aggregate metrics
                └── BenchmarkReport JSON
```

## Prerequisites

- an absolute dataset root outside the repository,
- an absolute UTF-8 JSON manifest path,
- legally controlled audio and annotations,
- a source commit SHA,
- an absolute output path under an ignored local artifact directory.

Do not commit dataset audio, private annotations or raw reports containing sensitive file names.

## Manifest

Copy `docs/examples/mir-benchmark-manifest.example.json` outside the repository or into a private ignored workspace and replace all placeholder evidence.

Every item path is relative to `--dataset-root`. Absolute paths and path escapes are rejected.

## Run

```bash
PYTHONDONTWRITEBYTECODE=1 \
python3 scripts/run_mir_benchmark.py \
  --manifest "/absolute/path/manifests/private-dj-v1.json" \
  --dataset-root "/absolute/path/datasets/private-dj-v1" \
  --provider librosa \
  --source-commit "$(git rev-parse HEAD)" \
  --output "$(pwd)/artifacts/mir/private-dj-v1-librosa.json"
```

Only copy the command itself. Do not copy the terminal prompt or command output back into the shell.

## Report Rules

The report contains:

- schema and manifest digest,
- dataset identity and license label,
- source commit,
- Python/platform evidence,
- provider and algorithm versions,
- one row per attempted track,
- controlled and uncontrolled failures,
- BPM exact/half-double/miss categories,
- exact/relative/adjacent/incompatible key categories,
- energy rank correlation,
- median and p95 runtime,
- proposed acceptance gates.

`decision_status` always remains `manual_review_required`. A green report cannot automatically switch the production provider.

## Safety

- Keep dataset roots read-only where practical.
- Review manifest and dataset checksums before each official run.
- The runner re-resolves each source and confirms it remains inside the dataset root.
- Provider failures remain in the report; they are never silently dropped.
- Store raw reports under ignored `artifacts/` storage.
- Commit only redacted aggregate reports after an explicit review.

## Interpretation

Unit and synthetic tests prove harness behavior. Production-provider selection additionally requires:

1. public licensed reference datasets,
2. a private DJ evaluation collection,
3. runtime and memory evidence on target hardware,
4. human DJ review,
5. packaging and licensing approval,
6. an explicit decision record.
