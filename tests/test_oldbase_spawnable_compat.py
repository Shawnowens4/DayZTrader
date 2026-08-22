import unittest
from pathlib import Path


class OldbaseSpawnableCompatContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("dxemb/web/templates/oldbase.html").read_text(encoding="utf-8")

    def test_spawnable_compat_parser_exists(self):
        self.assertIn("function parseSpawnableCompat(text)", self.source)
        self.assertIn("querySelectorAll('type[name]')", self.source)

    def test_parser_uses_item_name_inside_attachments_and_cargo(self):
        self.assertIn("attNode.querySelectorAll('item[name]')", self.source)
        self.assertIn("cargoNode.querySelectorAll('item[name]')", self.source)

    def test_compat_preserves_attachments_vs_cargo_separation(self):
        self.assertIn("attachments: attachments", self.source)
        self.assertIn("cargo: cargo", self.source)
        self.assertIn("all: unique(attachments.concat(cargo).map((entry) => entry.name))", self.source)

    def test_chance_attribute_captured(self):
        self.assertIn("chance: itemNode.getAttribute('chance') || '1.00'", self.source)

    def test_compat_exposed_in_catalog_state(self):
        self.assertIn("state.catalog.compat = spawnFile?.compat || null", self.source)

    def test_spawnable_list_derived_from_compat(self):
        self.assertIn("Object.values(spawnFile.compat).flatMap((c) => c.all)", self.source)

    def test_gunChildren_retained_as_fallback(self):
        self.assertIn("const gunChildren = {", self.source)
        self.assertIn("Fallback attachment map for unloaded or unmapped", self.source)

    def test_old_dead_selectors_removed(self):
        self.assertNotIn("extractXmlNames(text, 'attachment[name]'", self.source)
        self.assertNotIn("extractXmlNames(text, 'cargo[name]'", self.source)

    def test_new_live_selectors_present(self):
        self.assertIn("extractXmlNames(text, 'attachments item[name]'", self.source)
        self.assertIn("extractXmlNames(text, 'cargo item[name]'", self.source)


if __name__ == "__main__":
    unittest.main()
