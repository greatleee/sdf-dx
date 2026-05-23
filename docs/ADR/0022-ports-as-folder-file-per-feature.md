# ADR-0022: Ports — folder with file-per-feature

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

Initial convention placed all of a BC's port Protocols in a single `contexts/<bc>/ports.py` module. The argument for one file: short context window, fast-scan in code review, single import statement (`from contexts.<bc>.ports import LineStateReader, LineEventWriter`).

That argument holds only at low Port count. Phase 1 (single-factory vertical slice) already projects 4–6 ports per BC (`LineStateReader`, `LineEventWriter`, `UnitOfWork`, plus future cross-system reader and event publisher). Phase 3 (configuration BC) adds more. Past ~5 ports, single-file scan stops being faster — readers grep for the Protocol name, and the file becomes a long scroll instead of a fast scan.

The reference impl (`the reference codebase`) uses folder + file-per-feature: `ports/orders.py`, `ports/unit_of_work.py`, `ports/audit_log.py`, etc. Each file holds the Port Protocol plus the closely-related types (literals, projection records) that only that Port cares about. File size stays bounded; navigation is by name (open the file matching the Port's noun); diff churn is localized.

The cost of the folder layout is a one-line `__init__.py` if re-exports are wanted, and slightly longer import statements. Both are minor and one-time.

There is one subtlety: **what about Ports that span features?** `UnitOfWork` is the obvious case — it exposes per-feature repo attributes drawn from several Port files. The solution is to let `ports/unit_of_work.py` import the per-feature Port types it composes; the UoW file lives alongside the others, not in a special location.

Cross-cutting Ports (`ClockPort` per ADR-0021) live in `shared_kernel/ports/<name>.py`, not in any BC. They follow the same file-per-feature rule, one Protocol per file.

## Decision

**Location**: `contexts/<bc>/ports/` is a folder, not a module.

**Granularity**: one file per Port Protocol (or per closely-related Port pair, e.g., `<Noun>Reader` + `<Noun>Writer` that share a projection type). File names are the Port's noun in snake_case, no suffix:

```
contexts/monitoring/
├─ domain/
├─ ports/
│  ├─ __init__.py
│  ├─ line_state.py        # LineStateReader, LineStateWriter, LineStateProjection
│  ├─ line_event.py        # LineEventWriter, LineEvent literals
│  ├─ unit_of_work.py      # UnitOfWork Protocol + per-feature repo attributes
│  └─ cross_system.py      # cross-system reader (e.g., legacy DB), if needed
├─ application/
└─ adapters/
```

**`__init__.py`**: optional re-exports for ergonomic imports. Authors choose per BC; both `from contexts.monitoring.ports import LineStateReader` and `from contexts.monitoring.ports.line_state import LineStateReader` are valid. If `__init__.py` re-exports, it must explicitly list names with `__all__` to keep the surface intentional.

**Cross-cutting Ports** (e.g., `ClockPort`): `shared_kernel/ports/<name>.py`. Same file-per-feature rule, same naming convention.

**UoW**: `contexts/<bc>/ports/unit_of_work.py` per ADR-0020. Imports the per-feature Port types it composes from sibling files in the same folder.

**Adapter side mirrors structure but does not require 1:1 file-per-port.** A single adapter file may implement multiple Ports from the BC if they map to one storage subsystem (e.g., `contexts/monitoring/adapters/postgres_line.py` may implement both `LineStateReader` and `LineEventWriter`). The Port-side discipline is file-per-feature; the Adapter-side discipline is per-subsystem.

## Consequences

### Positive
- Port file size stays bounded as Port count grows.
- Navigation by noun: `open contexts/monitoring/ports/line_state.py` is faster than scrolling a long `ports.py`.
- Per-file diffs reduce review surface — adding a Port method touches one file, not the catch-all.
- Reference alignment with `the reference codebase`'s `ports/<feature>.py` shape (single-BC there; per-BC here).
- UoW Protocol gets to compose per-feature Ports by ordinary import, with no special module location.

### Negative / Trade-offs
- One more layer of directory traversal for new contributors learning the BC's surface. Mitigated by the noun-naming convention — the file name *is* the Port's identity.
- `__init__.py` re-exports vs deep imports is a per-BC style choice; without a project-wide rule, mixed styles can appear. The expectation is each BC commits to one style.
- Imports get longer if deep paths are used directly. Tooling (IDE auto-import, ruff isort) makes this a non-issue in practice.

## Migration Path

Forward (from `contexts/<bc>/ports.py` to `contexts/<bc>/ports/`):

1. Create `contexts/<bc>/ports/` folder and `__init__.py`.
2. Split each Port (or Port pair) into its own file under the new folder.
3. If `__init__.py` re-exports, update it.
4. Existing call sites: `from contexts.<bc>.ports import X` keeps working if `__init__.py` re-exports; otherwise mechanical rewrite to the deep path.

There are no production call sites yet (Phase 1 is pre-implementation for most BCs), so the migration is greenfield.

Reversal (back to single-file Ports) would mean concatenating the folder's files. Mechanical, and the loss is navigation ergonomics at scale.

## Sources

- `ports/` — reference impl folder layout.
- Python packaging — folder-as-package with `__init__.py` semantics. https://docs.python.org/3/tutorial/modules.html#packages
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §1.2 (folder layout) + §3.2 (cross-BC sync queries — import paths), `docs/ADR/0020-unit-of-work.md`, `docs/ADR/0021-clockport-protocol-standardized.md`, `docs/plans/2026-05-23-reference-codebase-alignment-plan.md` §10.
