import unittest
from pathlib import Path


class OldbaseModalCompatEnforcementContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("dxemb/web/templates/oldbase.html").read_text(encoding="utf-8")

    def test_modal_resolves_per_parent_upload_compatibility(self):
        self.assertIn("function resolveParentCompat(name, fallbackChildren = [])", self.source)
        self.assertIn("const xmlCompat = compat[name]", self.source)
        self.assertIn("source: 'cfgspawnabletypes.xml'", self.source)

    def test_modal_persists_real_child_classes_not_placeholder_labels(self):
        self.assertIn("modal.dataset.cargoChildren = JSON.stringify(childNames)", self.source)
        self.assertIn("const modalChildren = JSON.parse(modal?.dataset.cargoChildren || '[]')", self.source)
        self.assertNotIn("['Attachment', 'Cargo']", self.source)

    def test_uploaded_xml_is_preferred_over_fallback(self):
        self.assertIn("if (xmlCompat) {", self.source)
        self.assertIn("No cfgspawnabletypes.xml rule exists for this parent", self.source)
        self.assertIn("Fallback attachment map for unloaded or unmapped", self.source)

    def test_add_with_children_uses_modal_validated_children(self):
        self.assertIn("addQuickItem({ name: cargoName, type: cargoType, children: modalChildren }, true)", self.source)
        self.assertIn("has no validated child compatibility loaded", self.source)
        self.assertNotIn("|| ['Battery9V', 'DuctTape']", self.source)

    def test_manual_attachment_nesting_is_compatibility_guarded(self):
        self.assertIn("const allowedChildren = resolveParentCompat(parent.name, parent.children || []).all", self.source)
        self.assertIn("if (!allowedChildren.includes(name))", self.source)
        self.assertIn("it is not compatible with ${parent.name} in cfgspawnabletypes.xml", self.source)

    def test_attachment_cards_use_the_shared_parent_compatibility_resolver(self):
        self.assertIn("const activeCompat = active ? resolveParentCompat(active.name, active.children || [])", self.source)
        self.assertIn("const suggestions = activeCompat.attachments || []", self.source)
        self.assertIn("XML attachment", self.source)
        self.assertIn("No compatible attachments are loaded for", self.source)
        self.assertNotIn("|| ['Battery9V', 'DuctTape', 'Rag']", self.source)


if __name__ == "__main__":
    unittest.main()
