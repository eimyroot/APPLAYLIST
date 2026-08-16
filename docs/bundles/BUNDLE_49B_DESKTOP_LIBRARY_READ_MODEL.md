# Bundle 49B — Desktop Library Read Model and Safe Renderer UX

## Status

Implementation slice for issue #100 on canonical base `bc6fd0ab2fa88c21af3f2bddeb8df28b641b92bd`.

## Product value

The existing secure desktop import command already returns bounded track and issue DTOs. Bundle 49B makes those results inspectable without adding renderer filesystem, shell, network or database authority.

## Schema tree

```text
native folder selection
  -> opaque LibraryRootCapability
  -> library_import_root
  -> DesktopLibraryImportResult
       |- tracks[]: safe track DTOs
       `- issues[]: bounded issue DTOs
  -> renderer validation
  -> semantic library table / empty state / issue list
```

## Changed boundary

```text
BEFORE
choose -> import -> counts summary

AFTER
choose -> import -> counts summary
                 -> imported track read model
                 -> bounded issue presentation
                 -> explicit empty/error/result states
```

No host command, Tauri capability, sidecar protocol or persistence contract changes in this slice.

## Security invariants

- renderer invoke set remains exactly `library_choose_root` and `library_import_root`;
- renderer receives no generic filesystem or shell API;
- renderer performs no network call;
- canonical paths remain host-side and are not rendered;
- only safe `file_name` values from the existing DTO are displayed;
- DOM output uses created nodes and `textContent`, never HTML injection sinks;
- local stylesheet is compatible with the existing `style-src 'self'` CSP.

## Acceptance evidence expected

- Python renderer contract tests pass;
- PR Guard passes;
- desktop proof jobs applicable to changed renderer assets pass;
- exact PR head has no unresolved review threads before merge consideration.

## Out of scope

- streaming import progress;
- active cancellation command/lifecycle;
- background job persistence;
- analysis inspector;
- provider authority change;
- signing, notarization, updater or release distribution;
- merge authorization.

## Follow-up

Bundle 49C should add a bounded import job lifecycle with progress and cancellation. Bundle 50 starts only after Bundle 49 acceptance is complete.

## Rollback

Revert the isolated Bundle 49B commit. The slice has no database migration and adds no new runtime authority.
