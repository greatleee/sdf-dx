"""Application settings loaded from the environment (pydantic-settings).

Env var names match docker-compose (``PG_DSN`` / ``KAFKA_BOOTSTRAP``, the same
unprefixed convention the ingest service uses). pydantic-settings defaults
suffice: empty env_prefix + case-insensitive matching map the fields to those
vars. Settings live at the composition boundary — never imported by the
functional core.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


# `disallow_any_explicit` (pyproject) flags the Any-valued `SettingsConfigDict`
# TypedDict that BaseSettings carries — an unavoidable artifact of the
# rule-mandated config tool (backend-code-architecture §5), not our own typing.
# The ignore is scoped to this one line; strictness stays on everywhere else.
class Settings(BaseSettings):  # type: ignore[explicit-any]
    pg_dsn: str = "postgresql://sdf:sdf@localhost:5432/sdf"
    kafka_bootstrap: str = "localhost:9092"
