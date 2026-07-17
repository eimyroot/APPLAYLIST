# APPLAYLIST Target Architecture v1

## Status

Superseded by [`APPLAYLIST_TARGET_ARCHITECTURE_V2.md`](APPLAYLIST_TARGET_ARCHITECTURE_V2.md) in Bundle 47.

The original product-first architecture remains available in Git history. Version 2 preserves its Python domain/provider/repository boundaries and adds the accepted desktop/web hybrid topology:

```text
React renderer
  → typed Tauri desktop core
  → authenticated packaged Python sidecar
  → existing APPLAYLIST application services
```

Use the following canonical documents for new implementation decisions:

- [`ADR_BUNDLE_47_DESKTOP_SHELL.md`](ADR_BUNDLE_47_DESKTOP_SHELL.md)
- [`APPLAYLIST_DESKTOP_SECURITY_CONTRACT_V1.md`](APPLAYLIST_DESKTOP_SECURITY_CONTRACT_V1.md)
- [`APPLAYLIST_TARGET_ARCHITECTURE_V2.md`](APPLAYLIST_TARGET_ARCHITECTURE_V2.md)
- [`../roadmap/APPLAYLIST_PRODUCT_ROADMAP_41_54.md`](../roadmap/APPLAYLIST_PRODUCT_ROADMAP_41_54.md)
