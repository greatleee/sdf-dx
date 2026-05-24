#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
"""Domain suppression-allowlist guard.

The functional core is the most drift-expensive code in the repo: a single
inline `# noqa` or `# type: ignore` there silently relaxes the very purity the
import-linter / AST checks exist to enforce. import-linter and the AST call-site
checks already cannot be inline-suppressed; this script extends that property to
ruff and mypy across the domain layer.

Scans every `*.py` under:
  - `apps/*/src/**/domain/`
  - any `apps/*/src/**/shared_kernel/`

FAILS (exit 1, listing each offending file:line) if any line contains a
`# noqa` or `# type: ignore` suppression. PASSES (exit 0) with a one-line
summary otherwise — including the case where no domain dirs exist yet on this
branch (treated as a clean pass with a note).

Stdlib only; globs via pathlib.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"

# Matches a ruff `# noqa` (bare or coded) or a mypy `# type: ignore` suppression.
SUPPRESS_RE = re.compile(r"#\s*(noqa|type:\s*ignore)\b", re.IGNORECASE)


def collect_domain_files() -> list[Path]:
    """Every *.py under a `domain/` or `shared_kernel/` dir within `apps/*/src/`."""
    if not APPS_DIR.exists():
        return []
    files: set[Path] = set()
    for src in APPS_DIR.glob("*/src"):
        for marker in ("domain", "shared_kernel"):
            for d in src.rglob(marker):
                if d.is_dir():
                    files.update(d.rglob("*.py"))
    return sorted(files)


def main() -> int:
    files = collect_domain_files()

    if not files:
        print("OK: no domain/shared_kernel sources found yet — nothing to guard.")
        return 0

    offenders: list[str] = []
    for f in files:
        for lineno, line in enumerate(
            f.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if SUPPRESS_RE.search(line):
                offenders.append(f"{f.relative_to(ROOT)}:{lineno}: {line.strip()}")

    if offenders:
        print("Domain suppression check FAILED:", file=sys.stderr)
        print(
            "  domain/ and shared_kernel/ must never inline-silence a check "
            "(# noqa / # type: ignore).",
            file=sys.stderr,
        )
        for off in offenders:
            print(f"  - {off}", file=sys.stderr)
        return 1

    print(f"OK: {len(files)} domain/shared_kernel file(s) free of inline suppressions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
