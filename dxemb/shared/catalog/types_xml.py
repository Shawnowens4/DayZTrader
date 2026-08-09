from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import CatalogItem


class TypesXmlParseError(ValueError):
    """Raised when the source XML is malformed or not allowed."""


@dataclass(slots=True)
class ParsedTypeRecord:
    classname: str
    display_name: str
    category: str | None
    subcategory: str | None
    nominal: int | None
    lifetime: int | None
    restock: int | None
    min_count: int | None
    quant_min: int | None
    quant_max: int | None
    cost: int | None
    categories: list[str]
    usages: list[str]
    values: list[str]
    flags: dict[str, str]
    evidence_locator: str
    malformed_fields: list[str]


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
    records = parse_types_xml_records(path)
    out: list[CatalogItem] = []

    for record in records:
        item = CatalogItem(
            classname=record.classname,
            display_name=record.display_name,
            category=record.category,
            subcategory=record.subcategory,
            nominal=record.nominal,
            lifetime=record.lifetime,
            restock=record.restock,
            min_count=record.min_count,
            quant_min=record.quant_min,
            quant_max=record.quant_max,
            cost=record.cost,
            is_enabled=False,
        )
        out.append(item)

    return out


def parse_types_xml_records(path: str | Path | None = None) -> list[ParsedTypeRecord]:
    """Parse DayZ types.xml into explicit source records for import/audit tooling."""
    resolved = resolve_types_xml_path(str(path) if path else None)
    root = _parse_types_root(resolved)

    out: list[ParsedTypeRecord] = []
    for idx, type_node in enumerate(root.findall("type"), start=1):
        classname = (type_node.attrib.get("name") or "").strip()
        if not classname:
            continue

        malformed_fields: list[str] = []
        nominal = _to_int(_child_text(type_node, "nominal"), "nominal", malformed_fields)
        lifetime = _to_int(_child_text(type_node, "lifetime"), "lifetime", malformed_fields)
        restock = _to_int(_child_text(type_node, "restock"), "restock", malformed_fields)
        min_count = _to_int(_child_text(type_node, "min"), "min", malformed_fields)
        quant_min = _to_int(_child_text(type_node, "quantmin"), "quantmin", malformed_fields)
        quant_max = _to_int(_child_text(type_node, "quantmax"), "quantmax", malformed_fields)
        cost = _to_int(_child_text(type_node, "cost"), "cost", malformed_fields)

        categories = _all_named_children(type_node, "category")
        usages = _all_named_children(type_node, "usage")
        values = _all_named_children(type_node, "value")

        flags_node = type_node.find("flags")
        flags: dict[str, str] = {}
        if flags_node is not None:
            for key, value in flags_node.attrib.items():
                cleaned_key = (key or "").strip()
                cleaned_value = (value or "").strip()
                if cleaned_key:
                    flags[cleaned_key] = cleaned_value

        out.append(
            ParsedTypeRecord(
                classname=classname,
                display_name=_to_display_name(classname),
                category=categories[0] if categories else None,
                subcategory=usages[0] if usages else None,
                nominal=nominal,
                lifetime=lifetime,
                restock=restock,
                min_count=min_count,
                quant_min=quant_min,
                quant_max=quant_max,
                cost=cost,
                categories=categories,
                usages=usages,
                values=values,
                flags=flags,
                evidence_locator=f"/types/type[{idx}][@name='{classname}']",
                malformed_fields=malformed_fields,
            )
        )

    return out


def parse_types_xml_for_import(path: str | Path | None = None) -> dict[str, Any]:
    """Parse source XML and return importer-friendly metadata and records."""
    resolved = resolve_types_xml_path(str(path) if path else None)
    raw = _read_types_xml_bytes(resolved)
    root = _parse_types_root_from_bytes(raw)

    records = parse_types_xml_records(resolved)

    malformed_count = sum(1 for record in records if record.malformed_fields)
    return {
        "resolved_path": resolved,
        "source_basename": resolved.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "record_count": len(records),
        "malformed_count": malformed_count,
        "root_tag": root.tag,
        "records": records,
    }


def _read_types_xml_bytes(path: Path) -> bytes:
    if not path.exists():
        raise FileNotFoundError(f"types.xml not found: {path}")
    return path.read_bytes()


def _parse_types_root(path: Path) -> ET.Element:
    raw = _read_types_xml_bytes(path)
    return _parse_types_root_from_bytes(raw)


def _parse_types_root_from_bytes(raw: bytes) -> ET.Element:
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise TypesXmlParseError("types.xml contains disallowed DTD or ENTITY declarations")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise TypesXmlParseError(f"Malformed types.xml: {exc}") from exc

    if root.tag != "types":
        raise TypesXmlParseError(f"Unexpected root element '{root.tag}', expected 'types'")

    return root


def _first_named_child(node: ET.Element, tag_name: str) -> str | None:
    child = node.find(tag_name)
    if child is None:
        return None
    value = (child.attrib.get("name") or "").strip()
    return value or None


def _all_named_children(node: ET.Element, tag_name: str) -> list[str]:
    out: list[str] = []
    for child in node.findall(tag_name):
        value = (child.attrib.get("name") or "").strip()
        if value:
            out.append(value)
    return out


def _child_text(node: ET.Element, tag_name: str) -> str | None:
    child = node.find(tag_name)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _to_int(raw: str | None, field_name: str, malformed_fields: list[str]) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        malformed_fields.append(field_name)
        return None


def _to_display_name(classname: str) -> str:
    return classname.replace("_", " ").strip()
