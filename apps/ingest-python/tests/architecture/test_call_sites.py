"""Architecture call-site checks for the ingest functional core (ADR-0023 A1/A2).

`import-linter` bans module-level imports (pyproject `[tool.importlinter]`); this
AST check bans the *call-sites* it cannot express. `sdf_ingest.domain` must never
read the wall/monotonic clock or generate randomness/uuids inline — the shell
supplies those (backend-code-architecture §4). Importing the *types* is fine; only
the call expressions below are forbidden.

This mirrors `apps/api-python/tests/architecture/test_call_sites.py` so both
Python services enforce the same domain purity.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "sdf_ingest"
_DOMAIN_ROOT = _SRC / "domain"


def _domain_files() -> list[Path]:
    return sorted(_DOMAIN_ROOT.rglob("*.py")) if _DOMAIN_ROOT.exists() else []


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id
    return None


def _violations(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr = node.func.attr
        base = _base_name(node.func.value)
        if attr == "utcnow" and base == "datetime":
            found.append(f"datetime.utcnow() @ line {node.lineno}")
        elif attr == "now" and base == "datetime":
            found.append(f"datetime.now() @ line {node.lineno}")
        elif attr == "time" and base == "time":
            found.append(f"time.time() @ line {node.lineno}")
        elif attr in {"uuid4", "uuid1"} and base == "uuid":
            found.append(f"uuid.{attr}() @ line {node.lineno}")
    return found


def test_domain_has_no_forbidden_system_reads() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _domain_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if hits := _violations(tree):
            offenders[str(path.relative_to(_SRC))] = hits
    assert not offenders, f"forbidden system-read call-sites in functional core: {offenders}"


def test_domain_root_is_actually_scanned() -> None:
    # Guard against a path drift that would make the check pass vacuously.
    assert _domain_files(), f"no domain files found under {_DOMAIN_ROOT!r}"
