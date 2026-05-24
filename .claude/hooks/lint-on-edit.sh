#!/usr/bin/env bash
# .claude/hooks/lint-on-edit.sh
#
# PostToolUse hook — format + lint the single file Claude just edited.
#
# Design: "self-only" per folder. Each project folder triggers ONLY its own
# toolchain. Editing an api-python file never invokes ingest-python or Kotlin
# tooling. This keeps per-edit latency low and avoids cross-contamination.
#
# Invocation: called by Claude Code after Edit / Write / MultiEdit.
# Input:      JSON object on stdin; edited file path at .tool_input.file_path.
#
# Exit-code contract (PostToolUse semantics):
#   0  — no action needed, or tool ran and no remaining errors.
#        Formatting rewrites the file on disk; Claude re-reads it silently.
#   2  — tool ran, remaining lint errors exist. Output is printed to stderr
#        so Claude sees it and can attempt a fix.
#   (Any missing-tool / unmatched-path / parse-failure case exits 0 so that
#    edits are never blocked by a misconfigured environment.)
#
# NOTE: do NOT use `set -e`. Exit codes are handled deliberately below.
set -uo pipefail

# ---------------------------------------------------------------------------
# 1. Parse stdin — extract file_path
# ---------------------------------------------------------------------------
stdin_json="$(cat)"

if command -v jq >/dev/null 2>&1; then
  file="$(printf '%s' "$stdin_json" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
else
  file="$(printf '%s' "$stdin_json" | python3 -c \
    "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" \
    2>/dev/null || true)"
fi

# If extraction failed or path is empty / "null", nothing to do.
if [ -z "$file" ] || [ "$file" = "null" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# 2. Resolve repo root and compute repo-relative path
# ---------------------------------------------------------------------------
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  repo="$CLAUDE_PROJECT_DIR"
else
  repo="$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null || true)"
fi

if [ -z "$repo" ]; then
  # Not inside a git repo — nothing to do.
  exit 0
fi

# Strip trailing slash, then compute relative path.
repo="${repo%/}"
rel="${file#"$repo"/}"

# If stripping the prefix changed nothing, the file is outside the repo.
if [ "$rel" = "$file" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# 3. Route by path prefix — self-only, one toolchain per project folder
#
# bash `case` patterns don't support **, so we use if/elif with [[ ]] for
# prefix matching (supports any nesting depth) combined with extension checks.
# ---------------------------------------------------------------------------

# --- Helper: run ruff format + check on a single file using a specific venv ---
run_ruff() {
  local ruff_bin="$1"
  local target="$2"

  # Graceful degradation: if the venv binary is missing, skip silently.
  if [ ! -x "$ruff_bin" ]; then
    exit 0
  fi

  # Format first (rewrites file in place; always succeeds or we ignore failures).
  "$ruff_bin" format "$target" 2>/dev/null || true

  # Check (with --fix to auto-correct what format didn't handle).
  # Do NOT append `|| true` here: it would make `$?` capture `true`'s exit (always 0),
  # so the exit-2 feedback path below would never fire. `set -e` is off, so a non-zero
  # ruff exit does not abort the script — we capture and act on it deliberately.
  local check_out check_rc
  check_out="$("$ruff_bin" check --fix "$target" 2>&1)"
  check_rc=$?

  if [ "$check_rc" -ne 0 ] && [ -n "$check_out" ]; then
    printf '%s\n' "$check_out" >&2
    exit 2
  fi

  exit 0
}

# ---------------------------------------------------------------------------
# apps/api-python — Python files only, never inside .venv/
# ---------------------------------------------------------------------------
if [[ "$rel" == apps/api-python/* ]]; then
  # Skip venv-internal files and non-.py files.
  if [[ "$rel" == apps/api-python/.venv/* ]] || [[ "$rel" != *.py ]]; then
    exit 0
  fi
  run_ruff "$repo/apps/api-python/.venv/bin/ruff" "$file"

# ---------------------------------------------------------------------------
# apps/ingest-python — Python files only, never inside .venv/
# ---------------------------------------------------------------------------
elif [[ "$rel" == apps/ingest-python/* ]]; then
  if [[ "$rel" == apps/ingest-python/.venv/* ]] || [[ "$rel" != *.py ]]; then
    exit 0
  fi
  run_ruff "$repo/apps/ingest-python/.venv/bin/ruff" "$file"

# ---------------------------------------------------------------------------
# apps/ot-gateway-kotlin — Kotlin / KTS files, format-only via ktlint.
# Deliberately NOT running ./gradlew (too slow at ~15-20s per edit).
# ---------------------------------------------------------------------------
elif [[ "$rel" == apps/ot-gateway-kotlin/* ]]; then
  if [[ "$rel" != *.kt && "$rel" != *.kts ]]; then
    exit 0
  fi
  if command -v ktlint >/dev/null 2>&1; then
    ktlint -F "$file" 2>/dev/null || true
  else
    printf '[lint-on-edit] ktlint not installed — Kotlin formatting deferred to pre-commit\n' >&2
  fi
  exit 0

# ---------------------------------------------------------------------------
# apps/dashboard-react — stub (React app not scaffolded yet).
# Future command: pnpm --filter dashboard lint --fix "$file"
# ---------------------------------------------------------------------------
elif [[ "$rel" == apps/dashboard-react/* ]]; then
  # No-op until the React app is scaffolded.
  exit 0

# ---------------------------------------------------------------------------
# packages/contracts/codegen/ — generated output; never lint.
# ---------------------------------------------------------------------------
elif [[ "$rel" == packages/contracts/codegen/* ]]; then
  exit 0

# ---------------------------------------------------------------------------
# packages/contracts/openapi/*.yaml|yml — run spectral lint (best-effort).
# Only matches files directly in openapi/, not codegen/.
# ---------------------------------------------------------------------------
elif [[ "$rel" == packages/contracts/openapi/* ]] && \
     [[ "$rel" == *.yaml || "$rel" == *.yml ]]; then
  contracts_dir="$repo/packages/contracts"
  if [ -f "$contracts_dir/Makefile" ]; then
    lint_out="$(make -C "$contracts_dir" lint 2>&1)"
    lint_rc=$?
    if [ "$lint_rc" -ne 0 ] && [ -n "$lint_out" ]; then
      printf '%s\n' "$lint_out" >&2
      exit 2
    fi
  fi
  exit 0

# ---------------------------------------------------------------------------
# Everything else — docs, configs, root-level files, etc. No-op.
# ---------------------------------------------------------------------------
else
  exit 0
fi
