"""Cross-BC identifier value objects.

Each identifier is a frozen value object wrapping its raw representation, so the
type system rejects passing a :class:`LineId` where a :class:`MachineId` is
expected — identity confusion becomes a type error, not a runtime bug.

Per ADR-0017 / ADR-0021 the domain never *generates* identifiers
(``uuid.uuid4()`` is a forbidden system read inside ``shared_kernel`` — AST check
A2). IDs are only ever constructed from a value that already exists: parsed at
the Pydantic boundary (already ``UUID``-typed) or read back from storage.
Construction is therefore total over a ``UUID`` / slug and needs no
smart-constructor failure case.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantId:
    """Logical isolation boundary (GLOSSARY ``shared`` -> *Tenant*).

    Phase 1 has exactly one implicit tenant, :data:`DEFAULT_TENANT`.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            # An empty tenant slug is a shell contract breach, not a domain
            # outcome: ADR-0016 classes invariant violations as raisable.
            raise ValueError("TenantId must be a non-empty slug")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class FactoryId:
    """Identity of a topology *Factory* (ISA-95 Site)."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class LineId:
    """Identity of a production *Line* — shared by the monitoring and topology BCs.

    GLOSSARY records the deliberate name clash: a "Line" is a state-bearing object
    in ``monitoring`` and a structural node in ``topology``; the *identity* is the
    same, which is exactly why ``LineId`` lives in the shared kernel.
    """

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class MachineId:
    """Identity of a *Machine* (ISA-95 Work Unit)."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)


# Phase 1: a single implicit tenant (GLOSSARY ``shared`` -> *Tenant*; ADR-0003).
DEFAULT_TENANT: TenantId = TenantId("sdf_default")
