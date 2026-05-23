from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from sdf_api.shared_kernel.ids import (
    DEFAULT_TENANT,
    FactoryId,
    LineId,
    MachineId,
    TenantId,
)


def test_default_tenant_is_sdf_default() -> None:
    assert DEFAULT_TENANT == TenantId("sdf_default")
    assert str(DEFAULT_TENANT) == "sdf_default"


def test_uuid_ids_stringify_to_their_uuid() -> None:
    u = UUID("11111111-1111-1111-1111-111111111111")
    assert str(LineId(u)) == str(u)
    assert str(FactoryId(u)) == str(u)
    assert str(MachineId(u)) == str(u)


def test_same_uuid_different_id_types_are_not_equal() -> None:
    u = UUID(int=1)
    assert LineId(u) != MachineId(u)
    assert LineId(u) != FactoryId(u)


def test_same_type_same_value_is_equal_and_hashable() -> None:
    u = UUID(int=7)
    assert LineId(u) == LineId(u)
    assert len({LineId(u), LineId(u)}) == 1


def test_ids_are_frozen() -> None:
    line = LineId(UUID(int=1))
    with pytest.raises(FrozenInstanceError):
        line.value = UUID(int=2)  # type: ignore[misc]


@pytest.mark.parametrize("bad", ["", "   ", "\t"])
def test_tenant_rejects_blank_slug(bad: str) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        TenantId(bad)
