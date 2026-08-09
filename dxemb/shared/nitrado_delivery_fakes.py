"""In-memory fake interfaces for scheduler testing.

These fakes intentionally provide zero network capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from shared.nitrado_delivery_interfaces import DeliveryFileTransport
from shared.nitrado_delivery_interfaces import ProviderWindowRecord
from shared.nitrado_delivery_interfaces import RestartWindowProvider


@dataclass
class InMemoryRestartWindowProvider(RestartWindowProvider):
    windows: list[ProviderWindowRecord]

    def __post_init__(self) -> None:
        self.calls: list[dict] = []

    def fetch_restart_windows(self, now: datetime) -> list[ProviderWindowRecord]:
        self.calls.append({"method": "fetch_restart_windows", "now": now})
        return list(self.windows)


@dataclass
class InMemoryDeliveryFileTransport(DeliveryFileTransport):
    def __post_init__(self) -> None:
        self.calls: list[dict] = []

    def stage_artifact_metadata(
        self,
        *,
        order_id: int,
        artifact_hash: str,
        metadata: dict,
    ) -> dict:
        payload = {
            "method": "stage_artifact_metadata",
            "order_id": order_id,
            "artifact_hash": artifact_hash,
            "metadata": dict(metadata),
        }
        self.calls.append(payload)
        return {
            "mode": "dry-run",
            "recorded": True,
            "order_id": order_id,
            "artifact_hash": artifact_hash,
        }
