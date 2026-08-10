from __future__ import annotations

import sys
import unittest
from pathlib import Path

from flask import Flask, jsonify

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))

from web.local_auth import admin_or_higher
from web.local_auth import authenticated_player
from web.local_auth import get_resolved_identity
from web.local_auth import moderator_or_higher


class LocalAuthResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app = Flask(__name__)

        @app.get("/probe/player")
        @authenticated_player()
        def probe_player():
            identity = get_resolved_identity()
            return jsonify({"player_id": identity.player_id, "role": identity.role})

        @app.get("/probe/mod")
        @moderator_or_higher(message="moderator role is required")
        def probe_mod():
            identity = get_resolved_identity()
            return jsonify({"role": identity.role})

        @app.get("/probe/admin")
        @admin_or_higher(message="admin role is required")
        def probe_admin():
            identity = get_resolved_identity()
            return jsonify({"role": identity.role})

        cls.client = app.test_client()

    def test_player_identity_resolves_from_header(self) -> None:
        response = self.client.get("/probe/player", headers={"X-DXEMB-PLAYER-ID": "local:one"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["player_id"], "local:one")

    def test_player_identity_resolves_from_query(self) -> None:
        response = self.client.get("/probe/player?discord_user_id=local:two")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["player_id"], "local:two")

    def test_player_identity_mismatch_is_forbidden(self) -> None:
        response = self.client.get(
            "/probe/player?discord_user_id=local:two",
            headers={"X-DXEMB-PLAYER-ID": "local:one"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("identity mismatch", response.get_data(as_text=True))

    def test_player_identity_missing_is_unauthorized(self) -> None:
        response = self.client.get("/probe/player")
        self.assertEqual(response.status_code, 401)
        self.assertIn("player identity is required", response.get_data(as_text=True))

    def test_moderator_and_admin_role_checks(self) -> None:
        blocked = self.client.get("/probe/mod")
        mod_ok = self.client.get("/probe/mod", headers={"X-DXEMB-ROLE": "moderator"})
        admin_blocked = self.client.get("/probe/admin", headers={"X-DXEMB-ROLE": "moderator"})
        admin_ok = self.client.get("/probe/admin?as_role=admin")

        self.assertEqual(blocked.status_code, 403)
        self.assertIn("moderator role is required", blocked.get_data(as_text=True))
        self.assertEqual(mod_ok.status_code, 200)
        self.assertEqual(admin_blocked.status_code, 403)
        self.assertIn("admin role is required", admin_blocked.get_data(as_text=True))
        self.assertEqual(admin_ok.status_code, 200)


if __name__ == "__main__":
    unittest.main()
