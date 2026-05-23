"""Tests for topology Factory value object."""

from __future__ import annotations

import dataclasses
from uuid import UUID

import pytest

from sdf_api.contexts.topology.domain.factory import Factory
from sdf_api.shared_kernel.ids import FactoryId


def _factory_id(n: int = 1) -> FactoryId:
    return FactoryId(UUID(int=n))


class TestFactory:
    def test_constructs_with_expected_fields(self) -> None:
        fid = _factory_id(1)
        f = Factory(id=fid, name="Seoul Plant", timezone="Asia/Seoul", locale="ko-KR")
        assert f.id == fid
        assert f.name == "Seoul Plant"
        assert f.timezone == "Asia/Seoul"
        assert f.locale == "ko-KR"

    def test_fields_accessible(self) -> None:
        f = Factory(id=_factory_id(2), name="Berlin Hub", timezone="Europe/Berlin", locale="de-DE")
        assert f.timezone == "Europe/Berlin"
        assert f.locale == "de-DE"

    def test_frozen_raises_on_assignment(self) -> None:
        f = Factory(id=_factory_id(3), name="Plant", timezone="UTC", locale="en-US")
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.name = "other"  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        fid = _factory_id(4)
        a = Factory(id=fid, name="X", timezone="UTC", locale="en-US")
        b = Factory(id=fid, name="X", timezone="UTC", locale="en-US")
        assert a == b

    def test_inequality_on_differing_field(self) -> None:
        fid = _factory_id(5)
        a = Factory(id=fid, name="X", timezone="UTC", locale="en-US")
        b = Factory(id=fid, name="Y", timezone="UTC", locale="en-US")
        assert a != b
