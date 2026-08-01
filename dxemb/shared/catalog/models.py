from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CatalogItem:
    """Normalized trader item derived from DayZ types.xml."""

    classname: str
    display_name: str
    category: str | None = None
    subcategory: str | None = None
    nominal: int | None = None
    lifetime: int | None = None
    restock: int | None = None
    min_count: int | None = None
    quant_min: int | None = None
    quant_max: int | None = None
    cost: int | None = None
    is_enabled: bool = True
