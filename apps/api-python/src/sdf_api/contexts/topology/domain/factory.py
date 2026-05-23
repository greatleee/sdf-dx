"""ISA-95 Site; timezone/locale carried as strings — resolving/validating them is a boundary
concern, the domain trusts the shape it is given.
"""

from __future__ import annotations

from dataclasses import dataclass

from sdf_api.shared_kernel.ids import FactoryId


@dataclass(frozen=True, slots=True)
class Factory:
    id: FactoryId
    name: str
    timezone: str  # IANA zone name, e.g. "Asia/Seoul"
    locale: str  # BCP-47 tag, e.g. "ko-KR"
