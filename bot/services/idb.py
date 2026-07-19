"""
bot/services/idb.py — DayZIDB image resolution service stub.

Phase 1: Interface contract only. resolve() always returns the default thumb.
Phase 2: Real implementation — fetches DayZIDB manifest, caches results,
         respects DB override rows in idb_mappings.

Import path: bot.services.idb
"""
from __future__ import annotations


class IDBService:
    """
    Resolves DayZ class names to DayZIDB WebP thumbnail URLs.

    Phase 1 behavior: returns DEFAULT_THUMB for every input.
    Phase 2 behavior: loads JSON manifest from DayZIDB repo, checks
                      idb_mappings table for admin overrides.
    """

    DEFAULT_THUMB = "assets/default_item.webp"

    def __init__(self):
        # TODO Phase 2: accept settings dict and db_path; load manifest on init
        self._cache: dict[str, str] = {}

    async def resolve(self, class_name: str) -> str:
        """
        Return WebP thumbnail URL for a DayZ class name.
        Returns DEFAULT_THUMB if not found.
        Phase 1: always returns DEFAULT_THUMB.
        """
        # TODO Phase 2: check DB override -> check cache -> check manifest -> fallback
        return self.DEFAULT_THUMB

    async def resolve_many(self, class_names: list[str]) -> dict[str, str]:
        """
        Bulk resolve. Returns {class_name: url} dict.
        Phase 1: all values are DEFAULT_THUMB.
        """
        # TODO Phase 2: single-pass manifest lookup
        return {name: self.DEFAULT_THUMB for name in class_names}

    async def refresh_cache(self) -> None:
        """
        Re-fetch manifest from DayZIDB repo and rebuild cache.
        Phase 1: no-op.
        """
        # TODO Phase 2: aiohttp GET to repo_raw_base + manifest_path
        pass
