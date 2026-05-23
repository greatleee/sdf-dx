"""ISA-95 Work Unit; the 5 kinds are the Phase-1 line composition (GLOSSARY topology->Machine);
addressed on the edge by sparkplug_node_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sdf_api.shared_kernel.ids import LineId, MachineId


class MachineKind(StrEnum):
    PRESS = "press"
    WELD = "weld"
    PAINT = "paint"
    INSPECT = "inspect"
    PACK = "pack"


@dataclass(frozen=True, slots=True)
class Machine:
    id: MachineId
    line_id: LineId
    kind: MachineKind
    sparkplug_node_id: str
