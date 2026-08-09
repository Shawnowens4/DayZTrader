"""Provider and transport interfaces for delivery scheduler orchestration.

Interfaces are intentionally side-effect agnostic; concrete implementations for
this sprint are in-memory fakes only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ProviderWindowRecord:
    source_ref: str
    window_start_at: datetime
    window_end_at: datetime
    confidence: str
    observed_at: datetime
    expires_at: datetime
    is_conflicting: bool = False


class RestartWindowProvider(Protocol):
    def fetch_restart_windows(self, now: datetime) -> list[ProviderWindowRecord]:
        """Return cached/provider restart windows as plain records."""


class DeliveryFileTransport(Protocol):
    def stage_artifact_metadata(
        self,
        *,
        order_id: int,
        artifact_hash: str,
        metadata: dict,
    ) -> dict:
        """Record a dry-run staging action and return metadata only."""
