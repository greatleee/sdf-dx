"""Architecture call-site checks (ADR-0023 — AST checks A1 / A2).

`import-linter` bans *module-level imports*; these AST checks ban *call-sites*
that import-linter cannot express. The functional core
(`contexts/*/domain` + `shared_kernel`) must never read the wall/monotonic clock
or generate randomness/uuids inline — those reads are injected (ADR-0021
`ClockPort`; a future `UUIDPort` / `RandomPort`).

Note: importing the *types* (`from datetime import datetime`, `from uuid import
UUID`) is allowed; only the call expressions below are forbidden. Defining a
`now()` method (e.g. `ClockPort.now`) is a definition, not a call, and is fine.

A3 (`uow.session` outside `composition.py`) is intentionally not implemented yet:
no `UnitOfWork` exists in Phase 1 Section D (ADR-0020 lands with the adapters).
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "sdf_api"
_DOMAIN_ROOTS = [_SRC / "shared_kernel", *(_SRC / "contexts").glob("*/domain")]


def _domain_files() -> list[Path]:
    files: list[Path] = []
    for root in _DOMAIN_ROOTS:
        if root.exists():
            files.extend(root.rglob("*.py"))
    return sorted(files)


def _base_name(node: ast.expr) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _violations(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr = node.func.attr
        base = _base_name(node.func.value)
        if attr == "utcnow":  # A1 — datetime.utcnow() (unambiguous)
            found.append(f"datetime.utcnow() @ line {node.lineno}")
        elif attr == "now" and base == "datetime":  # A1 — datetime.now()
            found.append(f"datetime.now() @ line {node.lineno}")
        elif attr == "time" and base == "time":  # A1 — time.time()
            found.append(f"time.time() @ line {node.lineno}")
        elif attr in {"uuid4", "uuid1"} and base == "uuid":  # A2 — uuid.uuid4()/uuid1()
            found.append(f"uuid.{attr}() @ line {node.lineno}")
    return found


def test_domain_has_no_forbidden_system_reads() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _domain_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if hits := _violations(tree):
            offenders[str(path.relative_to(_SRC))] = hits
    assert not offenders, f"forbidden system-read call-sites in functional core: {offenders}"


def test_domain_roots_are_actually_scanned() -> None:
    # Guard: if the path drifts and we scan zero files, the check above passes
    # vacuously. This asserts the enforcement is live.
    assert _domain_files(), f"no domain files found under {_DOMAIN_ROOTS!r}"
