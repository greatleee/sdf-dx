"""Bounded contexts (ADR-0008).

Phase 1 is directory-based separation, not full BC ceremony: ``monitoring`` and
``topology`` are *candidate* bounded contexts. The only BC-level rule in force is
the import-linter independence contract (ADR-0023 #5) — no cross-BC imports
except shared identity via :mod:`sdf_api.shared_kernel`.
"""
