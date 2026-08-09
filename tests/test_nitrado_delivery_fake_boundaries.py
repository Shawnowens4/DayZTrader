from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))


class NitradoDeliveryFakeBoundaryTests(unittest.TestCase):
    def test_fake_and_interface_modules_have_no_network_imports(self) -> None:
        paths = [
            DXEMB_ROOT / "shared" / "nitrado_delivery_interfaces.py",
            DXEMB_ROOT / "shared" / "nitrado_delivery_fakes.py",
            DXEMB_ROOT / "shared" / "nitrado_delivery_scheduler_service.py",
        ]
        forbidden = [
            "import requests",
            "import httpx",
            "import aiohttp",
            "import ftplib",
            "import ftputil",
            "import paramiko",
            "import socket",
            "urllib.request",
            "subprocess",
        ]

        for path in paths:
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, source, msg=f"{path.name} unexpectedly includes {token}")

    def test_scheduler_service_has_no_restart_or_xml_write_tokens(self) -> None:
        source = (DXEMB_ROOT / "shared" / "nitrado_delivery_scheduler_service.py").read_text(encoding="utf-8")
        forbidden_tokens = [
            "restart_gameserver",
            "force_restart",
            "start_gameserver",
            "stop_gameserver",
            "write_xml",
            "upload_file",
            "delete_file",
            "spawn_vehicle",
            "spawn_item",
        ]

        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
