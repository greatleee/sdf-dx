#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Use-case coverage gate.

Checks:
  1. Every `docs/spec/use-cases/UC-*.md` file has well-formed front-matter with an `id`.
  2. The filename matches the front-matter `id` (UC-001 ⇄ UC-001-*.md).
  3. Every UC file's id appears as a row in `docs/spec/USE-CASES.md` (registry).
  4. Every UC id mentioned in the registry has a matching file.
  5. UCs with `status: implemented` declare a `related_e2e` path that exists on disk.

Exits 0 with a single OK line if everything passes; exits 1 listing each problem otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "docs" / "spec"
UC_DIR = SPEC_DIR / "use-cases"
REGISTRY = SPEC_DIR / "USE-CASES.md"

UC_ID_RE = re.compile(r"^UC-\d{3,}$")
REGISTRY_ROW_RE = re.compile(r"^\|\s*(UC-\d{3,})\s*\|")


def parse_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    block = text[4:end]
    try:
        loaded = yaml.safe_load(block)
    except yaml.YAMLError as e:
        raise ValueError(f"front-matter YAML error in {path}: {e}") from e
    if not isinstance(loaded, dict):
        raise ValueError(f"front-matter in {path} is not a mapping")
    return loaded


def collect_uc_files() -> list[Path]:
    if not UC_DIR.exists():
        return []
    return sorted(
        p for p in UC_DIR.glob("UC-*.md")
        if not p.name.startswith("_")
    )


def parse_registry_ids(text: str) -> set[str]:
    ids: set[str] = set()
    for line in text.splitlines():
        m = REGISTRY_ROW_RE.match(line)
        if m:
            ids.add(m.group(1))
    return ids


def main() -> int:
    errors: list[str] = []

    files = collect_uc_files()
    file_index: dict[str, tuple[Path, dict]] = {}

    for f in files:
        try:
            fm = parse_frontmatter(f)
        except ValueError as e:
            errors.append(str(e))
            continue
        if fm is None:
            errors.append(f"{f.relative_to(ROOT)}: no front-matter block")
            continue
        uc_id = fm.get("id")
        if not isinstance(uc_id, str) or not UC_ID_RE.match(uc_id):
            errors.append(f"{f.relative_to(ROOT)}: missing or malformed id (got {uc_id!r})")
            continue
        if not f.name.startswith(uc_id + "-"):
            errors.append(
                f"{f.relative_to(ROOT)}: filename does not start with '{uc_id}-'",
            )
        if uc_id in file_index:
            errors.append(f"{uc_id}: duplicate id in files "
                          f"{file_index[uc_id][0].name} and {f.name}")
            continue
        file_index[uc_id] = (f, fm)

    if not REGISTRY.exists():
        errors.append(f"{REGISTRY.relative_to(ROOT)}: registry file missing")
        registry_ids: set[str] = set()
    else:
        registry_ids = parse_registry_ids(REGISTRY.read_text(encoding="utf-8"))

    file_ids = set(file_index.keys())
    for uc in sorted(file_ids - registry_ids):
        errors.append(f"{uc}: per-UC file exists but no row in USE-CASES.md")
    for uc in sorted(registry_ids - file_ids):
        errors.append(f"{uc}: row in USE-CASES.md but no use-cases/{uc}-*.md")

    for uc_id, (f, fm) in file_index.items():
        status = fm.get("status")
        if status == "implemented":
            e2e = fm.get("related_e2e")
            if not isinstance(e2e, str) or not e2e.strip():
                errors.append(f"{uc_id}: status=implemented but related_e2e empty")
                continue
            if not (ROOT / e2e).exists():
                errors.append(f"{uc_id}: related_e2e path missing on disk: {e2e}")

    if errors:
        print("Use-case coverage check FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"OK: {len(file_index)} use case(s) consistent across registry, files, and E2E.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
