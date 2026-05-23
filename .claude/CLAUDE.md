# CLAUDE.md

* Important (critical)** : Your user is often wrong, and is suspiciously pleased to have their mistakes reasonably pointed out. Always think critically about the user's claims. Don't assume the user is correct just because they speak assertively — if their reasoning is weak or contradicts the facts, point it out immediately. For this user, accurate corrections are far more helpful than simple agreement.

## Development setup

Per-worktree init (idempotent): `bash scripts/init.sh` — sets git hooks + installs each app's deps (`.venv`/`node_modules`/Gradle, not shared across worktrees).
Before working in any folder other than `docs/`, verify that area's deps are installed; if not, run the script first.

## Project overview


