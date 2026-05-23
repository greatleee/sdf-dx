#!/usr/bin/env bash
# scripts/init.sh — initialize a fresh checkout or git worktree for development.
#
# Idempotent: safe to re-run. Each git worktree needs its own init because
# per-directory deps (.venv, node_modules, Gradle build/) are NOT shared across
# worktrees — only enabling hooks + installing deps makes a worktree buildable.
#
# Steps: (1) git hooks  (2) Python app venvs  (3) JS workspace  (4) Kotlin toolchain.
# Usage:  bash scripts/init.sh           # full init
#         SKIP_KOTLIN=1 bash scripts/init.sh   # skip the slow Gradle bootstrap
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
echo "== sdf-dx init :: $ROOT =="

# 1) Git hooks — contracts pre-commit (lint + codegen). Repo-wide config; the
#    relative path resolves per-worktree against each worktree root.
echo "-- git hooks: core.hooksPath -> .githooks"
git config core.hooksPath .githooks

# 2) Python apps — one uv-managed .venv per app (per-worktree, not shared).
for app in apps/api-python apps/ingest-python; do
  [ -f "$app/pyproject.toml" ] || continue
  echo "-- python: $app (uv venv + editable install)"
  ( cd "$app"
    # Pin 3.12 to match the project target (mypy/ruff target-version, CI), not
    # the machine's default interpreter.
    [ -d .venv ] || uv venv --python 3.12
    uv pip install -e ".[dev]" )
done

# 3) JS workspace — a single root install covers every pnpm-workspace member.
if [ -f pnpm-workspace.yaml ] && \
   [ -n "$(find apps packages -maxdepth 2 -name package.json -not -path '*/node_modules/*' 2>/dev/null)" ]; then
  echo "-- js workspace: pnpm install"
  pnpm install
else
  echo "-- js workspace: skip (no installable workspace package yet)"
fi

# 4) Kotlin — bootstrap the Gradle wrapper + resolve plugins. The dependency
#    cache (~/.gradle) is global, but this validates the wrapper and JDK 21.
if [ -z "${SKIP_KOTLIN:-}" ] && [ -x apps/ot-gateway-kotlin/gradlew ]; then
  echo "-- kotlin: apps/ot-gateway-kotlin (gradlew help)"
  jh="${JAVA_HOME:-}"
  if command -v /usr/libexec/java_home >/dev/null 2>&1; then
    jh="$(/usr/libexec/java_home -v 21 2>/dev/null || echo "${jh}")"
  fi
  ( cd apps/ot-gateway-kotlin && JAVA_HOME="${jh}" ./gradlew help -q ) \
    || echo "   WARN: gradle bootstrap failed — set JAVA_HOME to a JDK 21 and retry, or run with SKIP_KOTLIN=1"
else
  echo "-- kotlin: skip"
fi

echo "== init done =="
