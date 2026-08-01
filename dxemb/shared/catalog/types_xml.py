from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import CatalogItem


def resolve_types_xml_path(explicit_path: str | None = None) -> Path:
    """Resolve canonical types.xml path.

    Priority:
    1) explicit_path argument
    2) TYPES_XML_PATH environment variable
    3) bundled baseline file under shared/catalog/data/types.xml
    """
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    env_path = os.getenv("TYPES_XML_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()

    return (Path(__file__).resolve().parent / "data" / "types.xml").resolve()


def parse_types_xml(path: str | Path | None = None) -> list[CatalogItem]:
    """Parse DayZ types.xml into normalized catalog item rows."""
    resolved = resolve_types_xml_path(str(path) if path else None)
    if not resolved.exists():
        raise FileNotFoundError(f"types.xml not found: {resolved}")

    root = ET.parse(resolved).getroot()
    out: list[CatalogItem] = []

    for type_node in root.findall("type"):
        classname = (type_node.attrib.get("name") or "").strip()
        if not classname:
            continue

        category = _first_named_child(type_node, "category")
        subcategory = _first_named_child(type_node, "usage")

        item = CatalogItem(
            classname=classname,
            display_name=_to_display_name(classname),
            category=category,
            subcategory=subcategory,
            nominal=_to_int(_child_text(type_node, "nominal")),
            lifetime=_to_int(_child_text(type_node, "lifetime")),
            restock=_to_int(_child_text(type_node, "restock")),
            min_count=_to_int(_child_text(type_node, "min")),
            quant_min=_to_int(_child_text(type_node, "quantmin")),
            quant_max=_to_int(_child_text(type_node, "quantmax")),
            cost=_to_int(_child_text(type_node, "cost")),
            is_enabled=True,
        )
        out.append(item)

    return out


def _first_named_child(node: ET.Element, tag_name: str) -> str | None:
    child = node.find(tag_name)
    if child is None:
        return None
    value = (child.attrib.get("name") or "").strip()
    return value or None


def _child_text(node: ET.Element, tag_name: str) -> str | None:
    child = node.find(tag_name)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _to_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _to_display_name(classname: str) -> str:
    return classname.replace("_", " ").strip()
