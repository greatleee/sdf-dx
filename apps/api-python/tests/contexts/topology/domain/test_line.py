"""Tests for topology ProductionLine value object."""

from __future__ import annotations

import dataclasses
from uuid import UUID

import pytest

from sdf_api.contexts.topology.domain.line import ProductionLine
from sdf_api.contexts.topology.domain.machine import Machine, MachineKind
from sdf_api.shared_kernel.ids import FactoryId, LineId, MachineId


def _factory_id(n: int) -> FactoryId:
    return FactoryId(UUID(int=n))


def _line_id(n: int) -> LineId:
    return LineId(UUID(int=n))


def _machine_id(n: int) -> MachineId:
    return MachineId(UUID(int=n))


def _machine(mid: int, lid: LineId, kind: MachineKind = MachineKind.PRESS) -> Machine:
    return Machine(
        id=_machine_id(mid),
        line_id=lid,
        kind=kind,
        sparkplug_node_id=f"edge/{kind}-{mid:02d}",
    )


class TestProductionLine:
    def test_empty_machines_default(self) -> None:
        lid = _line_id(1)
        line = ProductionLine(id=lid, factory_id=_factory_id(1), name="Line A")
        assert line.machines == ()

    def test_valid_line_with_two_matching_machines(self) -> None:
        lid = _line_id(2)
        m1 = _machine(1, lid, MachineKind.PRESS)
        m2 = _machine(2, lid, MachineKind.WELD)
        line = ProductionLine(id=lid, factory_id=_factory_id(2), name="Line B", machines=(m1, m2))
        assert len(line.machines) == 2
        assert line.machines[0] == m1
        assert line.machines[1] == m2

    def test_machines_stored_as_tuple(self) -> None:
        lid = _line_id(3)
        m = _machine(1, lid, MachineKind.PAINT)
        line = ProductionLine(id=lid, factory_id=_factory_id(3), name="Line C", machines=(m,))
        assert isinstance(line.machines, tuple)

    def test_machine_wrong_line_id_raises(self) -> None:
        lid = _line_id(4)
        other_lid = _line_id(99)
        bad_machine = _machine(1, other_lid, MachineKind.INSPECT)
        with pytest.raises(ValueError, match="belongs to line"):
            ProductionLine(
                id=lid, factory_id=_factory_id(4), name="Line D", machines=(bad_machine,)
            )

    def test_duplicate_machine_ids_raises(self) -> None:
        lid = _line_id(5)
        mid = _machine_id(1)
        m1 = Machine(id=mid, line_id=lid, kind=MachineKind.PRESS, sparkplug_node_id="edge/press-01")
        m2 = Machine(id=mid, line_id=lid, kind=MachineKind.WELD, sparkplug_node_id="edge/weld-01")
        with pytest.raises(ValueError, match="duplicate machine ids"):
            ProductionLine(id=lid, factory_id=_factory_id(5), name="Line E", machines=(m1, m2))

    def test_frozen_raises_on_assignment(self) -> None:
        lid = _line_id(6)
        line = ProductionLine(id=lid, factory_id=_factory_id(6), name="Line F")
        with pytest.raises(dataclasses.FrozenInstanceError):
            line.name = "other"  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        lid = _line_id(7)
        fid = _factory_id(7)
        a = ProductionLine(id=lid, factory_id=fid, name="Line G")
        b = ProductionLine(id=lid, factory_id=fid, name="Line G")
        assert a == b
