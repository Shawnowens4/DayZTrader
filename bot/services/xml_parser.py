"""
bot/services/xml_parser.py — DayZ XML file parser stub.

Phase 1: Data classes and interface contracts only.
         All parse methods raise NotImplementedError.
Phase 2: Real xml.etree.ElementTree parsing of types.xml and events.xml.

Import path: bot.services.xml_parser
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TypesEntry:
    """One <type> element from types.xml."""
    class_name:       str
    nominal:          int = 0
    min:              int = 0
    lifetime:         int = 0
    restock:          int = 0
    quantmin:         int = -1
    quantmax:         int = -1
    category:         str = "misc"
    usages:           list[str] = field(default_factory=list)
    count_in_map:     int = 1
    count_in_hoarder: int = 0
    count_in_player:  int = 0
    count_in_cargo:   int = 0


@dataclass
class EventEntry:
    """One <event> element from events.xml."""
    name:     str
    nominal:  int = 0
    min:      int = 0
    lifetime: int = 0
    restock:  int = 0
    active:   int = 1


class XMLParserService:
    """
    Parses DayZ server XML files into structured Python objects.

    Phase 1: raises NotImplementedError on all parse methods.
    Phase 2: xml.etree.ElementTree implementation.
    """

    def parse_types(self, xml_path: str) -> list[TypesEntry]:
        """
        Parse a types.xml file. Excludes entries where count_in_map == 0.
        Phase 1: not implemented.
        """
        # TODO Phase 2: open file, parse with ElementTree, return list[TypesEntry]
        raise NotImplementedError("xml_parser.parse_types — Phase 2")

    def parse_types_from_string(self, xml_content: str) -> list[TypesEntry]:
        """
        Parse types.xml content from a string (e.g. fetched via Nitrado API).
        Phase 1: not implemented.
        """
        # TODO Phase 2: same logic as parse_types but from in-memory string
        raise NotImplementedError("xml_parser.parse_types_from_string — Phase 2")

    def parse_events(self, xml_path: str) -> list[EventEntry]:
        """
        Parse an events.xml file.
        Phase 1: not implemented.
        """
        # TODO Phase 2: open file, parse with ElementTree, return list[EventEntry]
        raise NotImplementedError("xml_parser.parse_events — Phase 2")
