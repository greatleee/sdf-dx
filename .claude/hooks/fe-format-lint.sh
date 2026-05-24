#!/usr/bin/env bash
# Claude Code PostToolUse hook — auto-format + lint a dashboard file right after
# an agent edits it, so LLM-introduced drift (ADR-0031) is caught at edit time,
# before git or CI. Scoped to apps/dashboard-react; a no-op for every other file.
#
# Wired in .claude/settings.json (PostToolUse, matcher Edit|Write|MultiEdit).
# Reads the hook JSON on stdin; needs `jq` + the dashboard's node_modules.
# Exit 0 = clean / skipped; exit 2 = Prettier failed or ESLint issues remain
# after --fix (stderr is fed back to the agent so it self-corrects same turn).
set -euo pipefail

payload=$(cat)

# jq is the clean way to read the edited path; degrade to a no-op if it's absent.
command -v jq >/dev/null 2>&1 || exit 0
file=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty')
[ -n "$file" ] || exit 0

# Act only on dashboard TS/TSX/CSS; everything else is none of our business.
case "$file" in
  *"/apps/dashboard-react/"*.ts | *"/apps/dashboard-react/"*.tsx | *"/apps/dashboard-react/"*.css) ;;
  *) exit 0 ;;
esac

root="${CLAUDE_PROJECT_DIR:-$(git -C "$(dirname "$file")" rev-parse --show-toplevel)}"
dash="$root/apps/dashboard-react"
if [ ! -d "$dash/node_modules" ]; then
  echo "[fe-hook] $dash/node_modules missing — run scripts/init.sh; skipping format/lint." >&2
  exit 0
fi

cd "$dash"

# Format always (Prettier owns formatting; --write is idempotent). Surface
# Prettier failures (parse/config errors) instead of letting the hook claim
# success while formatting silently didn't run (PR #18 review).
if ! prettier_report=$(pnpm exec prettier --write "$file" 2>&1); then
  {
    echo "[fe-hook] Prettier failed on $file (format drift not fixed):"
    echo "$prettier_report"
  } >&2
  exit 2
fi

# Lint only source TS/TSX — the flat config scopes rules to src/**; CSS is format-only.
case "$file" in
  *"/apps/dashboard-react/src/"*.ts | *"/apps/dashboard-react/src/"*.tsx)
    if ! report=$(pnpm exec eslint --fix "$file" 2>&1); then
      {
        echo "[fe-hook] ESLint issues remain in $file after auto-fix (ADR-0031 guard):"
        echo "$report"
        echo "[fe-hook] Fix the violation — do NOT add an eslint-disable (rules §11)."
      } >&2
      exit 2
    fi
    ;;
esac
exit 0
