"""Tests for topology Machine value object and MachineKind enum."""

from __future__ import annotations

import dataclasses
from uuid import UUID

import pytest

from sdf_api.contexts.topology.domain.machine import Machine, MachineKind
from sdf_api.shared_kernel.ids import LineId, MachineId


def _machine_id(n: int) -> MachineId:
    return MachineId(UUID(int=n))


def _line_id(n: int) -> LineId:
    return LineId(UUID(int=n))


class TestMachineKind:
    def test_has_exactly_five_members(self) -> None:
        assert set(MachineKind) == {
            MachineKind.PRESS,
            MachineKind.WELD,
            MachineKind.PAINT,
            MachineKind.INSPECT,
            MachineKind.PACK,
        }

    def test_string_values(self) -> None:
        assert MachineKind.PRESS == "press"
        assert MachineKind.WELD == "weld"
        assert MachineKind.PAINT == "paint"
        assert MachineKind.INSPECT == "inspect"
        assert MachineKind.PACK == "pack"


class TestMachine:
    def test_constructs_with_expected_fields(self) -> None:
        mid = _machine_id(1)
        lid = _line_id(10)
        m = Machine(id=mid, line_id=lid, kind=MachineKind.PRESS, sparkplug_node_id="edge/press-01")
        assert m.id == mid
        assert m.line_id == lid
        assert m.kind == MachineKind.PRESS
        assert m.sparkplug_node_id == "edge/press-01"

    def test_frozen_raises_on_assignment(self) -> None:
        m = Machine(
            id=_machine_id(2),
            line_id=_line_id(20),
            kind=MachineKind.WELD,
            sparkplug_node_id="edge/weld-01",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.kind = MachineKind.PAINT  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        mid = _machine_id(3)
        lid = _line_id(30)
        a = Machine(id=mid, line_id=lid, kind=MachineKind.PACK, sparkplug_node_id="edge/pack-01")
        b = Machine(id=mid, line_id=lid, kind=MachineKind.PACK, sparkplug_node_id="edge/pack-01")
        assert a == b
