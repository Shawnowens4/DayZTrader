import unittest
from pathlib import Path


class OldbaseBuilderControllerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("dxemb/web/templates/oldbase.html").read_text(encoding="utf-8")

    def test_private_tab_three_controller_is_archived_not_executable(self):
        self.assertIn("Retired duplicate Tab 3 controller.", self.source)
        self.assertIn("The active builder is window.__DZBuilderWorkflow", self.source)
        self.assertNotIn('<script id="tab3-clickable-blank-state-script"', self.source)
        self.assertNotIn('type="application/x-dayz-retired"', self.source)
        self.assertNotIn("const state = { quick: [], builds: [] };", self.source)

    def test_single_workflow_state_and_no_polling_rerender(self):
        self.assertEqual(self.source.count("const state = window.__DZBuilderWorkflow ||"), 1)
        self.assertIn("window.__DZBuilderWorkflow", self.source)
        self.assertNotIn("function wireWorkflowControls()", self.source)
        self.assertNotIn("if (qs('#configureMain:not(.hidden)')) renderQuickBuilder()", self.source)

    def test_catalog_restricted_items_are_marked_and_defended(self):
        self.assertIn("data-catalog-restricted", self.source)
        self.assertIn("nested cargo support is not implemented for this item", self.source)
        self.assertIn("catalog-restriction", self.source)

    def test_spawnable_membership_is_not_presented_as_child_compatibility(self):
        self.assertNotIn("spawnableNames.includes(name) ? ['Attachment', 'Cargo'] : []", self.source)
        self.assertIn("Spawnable membership is not authoritative child compatibility", self.source)

    def test_main_item_chance_edits_persist_to_workflow_state(self):
        self.assertIn("document.addEventListener('input'", self.source)
        self.assertEqual(self.source.count("state.quick[index].chance = chanceInput.value || '100%'"), 1)


if __name__ == "__main__":
    unittest.main()
