# APPLAYLIST Canonical Shadow Reader V1

## Status

```text
WB004E_IMPLEMENTATION=ISOLATED_CORE_SLICE
CANONICAL_READER_PRODUCT_PATH=NONE
CANONICAL_READER_ACTIVATION=NONE_BY_DEFAULT
LEGACY_ANALYSIS_AUTHORITY=ACTIVE
RUNTIME_AUTHORITY_SWITCH=NONE
PUBLIC_API_CHANGE=NONE
BACKFILL=NONE
WB004F_START=NONE
WB006D=HOLD
```

This document describes an internal, default-off WB004E component. It does not
declare a product-path integration or an authority cutover.

## Purpose

The canonical shadow reader is a bounded observer for future non-live parity
verification. Given an already-authoritative legacy `AnalysisRecord`, it may:

1. read the corresponding canonical persistence record by `track_id`;
2. reuse the WB004D canonical-to-legacy comparator;
3. write a bounded receipt for match, mismatch, canonical absence, or failure;
4. return the original legacy object unchanged.

## Components

- `CanonicalShadowReaderProfile`
  - defaults to disabled;
  - fails closed in `prod` and `production`;
  - requires an allowlisted non-live environment and an explicit receipt path.

- `CanonicalShadowReader`
  - accepts injected reader and receipt-sink protocols;
  - catches canonical read/comparison failures;
  - catches receipt-write failures;
  - never replaces or mutates the authoritative legacy result.

- `CanonicalShadowReadReceipt`
  - records stable identifiers, schema versions, comparison outcome, bounded
    correlation ID, matched fields, mismatched fields, duration, and error type;
  - excludes source paths and raw analysis payloads;
  - JSONL files are created with mode `0600`.

## Configuration contract

The component is not wired into an application or product request path.

A future explicitly authorized non-live caller may resolve:

```text
APP_ENV=development|test|staging|nonlive
APPLAYLIST_CANONICAL_SHADOW_READER_ENABLED=1
APPLAYLIST_CANONICAL_SHADOW_READER_RECEIPTS_PATH=<explicit non-live path>
```

Production environments always resolve the profile as disabled, even when the
enable flag is present.

## Failure behaviour

Canonical absence, canonical repository failure, identity mismatch, comparison
failure, and receipt-sink failure do not change the returned legacy object.
No canonical value becomes authoritative.

## Deferred work

The following remain outside this isolated slice:

- connection to `AnalysisRepository.get_by_track_id()` or another product seam;
- runtime activation in any caller;
- parity campaign execution;
- product endpoint, composer, ranking, or transition changes;
- WB004F and WB004G.
