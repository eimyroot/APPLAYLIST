# APPLAYLIST Third-Party Notices

## Purpose

APPLAYLIST is proprietary software, but it uses and evaluates third-party software that remains governed by its own licenses. This file is the repository-level notice and release-compliance index.

It is **not yet a complete installer notice bundle**. External commercial distribution remains blocked until the exact shipped dependency graph, native libraries, models, datasets, fonts, assets, and packaging tools have been resolved from lockfiles/build artifacts and the required upstream license texts and notices have been collected.

The authoritative engineering decision register is `docs/compliance/APPLAYLIST_LICENSE_DECISION_REGISTER_V1.md`.

## Current development/runtime components

The repository currently declares or evaluates the following material components. Exact versions and transitive/native dependencies must be taken from the release SBOM for any distributed build.

| Component | Role | Repository compliance state | Known upstream license family / action |
|---|---|---|---|
| Python | packaged sidecar/runtime | `approved_dev` | Python Software Foundation terms; preserve required notices for redistributed runtime |
| FastAPI | local/headless API transport | `approved_dev` | MIT; include upstream notice for shipped dependency set |
| Pydantic | validation/configuration | `approved_dev` | permissive upstream license; verify exact resolved package/version in SBOM |
| NumPy | numerical processing | `approved_dev` | BSD-family; include exact upstream notices and bundled native notices |
| SciPy | signal processing | `approved_dev` | BSD-family; include exact upstream notices and bundled native notices |
| SoundFile | audio decode boundary | `approved_dev` | audit Python package plus native `libsndfile` redistribution obligations before shipping |
| Librosa | baseline MIR candidate | `approved_dev` | ISC; distribution still depends on the complete native/transitive package review |
| TinyTag | read-only metadata | `approved_dev` | MIT; retain upstream notice and exact resolved version |
| Tauri 2 | target desktop shell | `approved_dev` | MIT/Apache-2.0 ecosystem; exact crates/plugins require SBOM and notice audit |
| React | target shared UI | `approved_dev` / target stack | MIT; verify exact resolved version and transitive packages |
| TypeScript | target UI toolchain | `approved_dev` / target stack | Apache-2.0; verify exact resolved version and toolchain distribution scope |
| PyInstaller or alternative freezer | packaged Python candidate | `review_required` | no production packaging approval until exact tool and obligations are recorded |
| Essentia | advanced MIR experiment | `experiment_only` | must not enter a commercial build without explicit licensing approval |
| Essentia pretrained models | optional model research | `review_required` | every model requires a separate license/provenance record |
| Tauri plugins | desktop capabilities | `review_required` until individually resolved | approve exact plugin/version/permissions and transitive dependencies before shipping |

The table is intentionally conservative. It does not grant permission to package a component merely because an upstream license family is named here.

## Components and materials outside the APPLAYLIST proprietary grant

The following are never automatically relicensed as proprietary APPLAYLIST code:

- third-party libraries and frameworks;
- native libraries and codecs;
- operating-system components and WebView runtimes;
- pretrained models and model weights;
- benchmark datasets and annotations;
- fonts, icons, photographs, audio, artwork, samples, or other media acquired under separate terms;
- donor/reference repository code;
- third-party APIs, SDKs, services, and proprietary DJ ecosystem formats.

Each remains subject to its own license, terms, copyright, database rights, trademark rights, or contractual restrictions.

## Donor/reference code

The current engineering register permits `4gray/iptvnator` only as an architecture reference. No code, branding, screenshots, media, IPTV/EPG logic, playback logic, provider logic, or other donor implementation may be copied into APPLAYLIST without file-level provenance and license review.

## Models and datasets

No model or dataset is approved for redistribution solely because it is publicly downloadable.

Before inclusion or use in commercial product evidence, record at minimum:

- exact name and version;
- source;
- copyright/owner;
- license or contractual terms;
- commercial-use permission;
- redistribution permission;
- model/dataset-specific restrictions;
- checksums and provenance;
- whether the material is packaged, downloaded separately, or used only for evaluation.

Dataset audio and non-redistributable annotations must remain outside source control.

## Release gate

Before any external desktop release, the release owner must:

1. generate complete SBOMs for JavaScript/TypeScript, Rust/Tauri, Python, frozen runtime, and native libraries;
2. confirm that no `experiment_only`, unresolved `review_required`, or otherwise prohibited dependency is packaged;
3. collect the complete upstream license/copyright/NOTICE texts required by the exact shipped artifacts;
4. identify dynamic/static linking, embedding, bundling, source-offer, relinking, or other redistribution obligations where applicable;
5. verify model, dataset, font, icon, artwork, and media rights separately from software-code licensing;
6. archive exact lockfiles and build provenance;
7. ensure no signing key, credential, token, or private customer/media data is embedded in source or release artifacts;
8. run the signed/notarized package on a clean supported system;
9. preserve the final SBOM and third-party notice bundle with the released version.

## No conflict with upstream rights

If this file conflicts with an applicable third-party license, the third-party license controls for that third-party component. APPLAYLIST's proprietary license applies only to rights the APPLAYLIST copyright holder(s) are legally entitled to license.
