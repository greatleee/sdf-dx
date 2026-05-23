"""ISA-95 Production Line (Work Center sub-type, DOMAIN-NOTES). Holds machines as an immutable
tuple. Enforces the two structural invariants the boundary cannot check — every machine belongs
to this line, and machine ids are unique — by raising. DELIBERATELY does NOT enforce a machine
count or required set of kinds: "5 machines, one of each kind" is Phase-1 simulator config, not
a universal topology law.

The intra-BC import of Machine from a sibling domain module is allowed — bc-independence only
forbids CROSS-BC imports.
"""

from __future__ import annotations

from dataclasses import dataclass

from sdf_api.contexts.topology.domain.machine import Machine
from sdf_api.shared_kernel.ids import FactoryId, LineId


@dataclass(frozen=True, slots=True)
class ProductionLine:
    id: LineId
    factory_id: FactoryId
    name: str
    machines: tuple[Machine, ...] = ()

    def __post_init__(self) -> None:
        for machine in self.machines:
            if machine.line_id != self.id:
                raise ValueError(
                    f"machine {machine.id} belongs to line {machine.line_id}, not {self.id}"
                )
        ids = [m.id for m in self.machines]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate machine ids on production line")
