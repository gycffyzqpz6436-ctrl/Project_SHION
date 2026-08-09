import unittest
from unittest.mock import Mock

from app.core.orchestrator import ShionOrchestrator
from app.memory.long_term import DisabledLongTermMemory
from app.models.registry import ModelRegistry
from app.tools.registry import ToolRegistry


class ShionArchitectureTests(unittest.TestCase):
    def test_unknown_and_disabled_tools_are_unavailable(self):
        registry = ToolRegistry()
        self.assertFalse(registry.invoke("web", {"query": "example"}).available)
        disabled = Mock()
        disabled.name = "vision"
        disabled.enabled = False
        registry.register(disabled)
        result = registry.invoke("vision", {"image": "untrusted"})
        self.assertFalse(result.available)
        disabled.invoke.assert_not_called()

    def test_orchestrator_is_conversation_only_placeholder(self):
        model = Mock()
        model.generate.return_value = ("reply", 12)
        orchestrator = ShionOrchestrator()
        result = orchestrator.respond(model, "session", "minimal", [], "hello")
        self.assertEqual(result, ("reply", 12))
        model.generate.assert_called_once_with("session", "minimal", [], "hello")
        self.assertEqual(
            orchestrator.capability_status(),
            {"long_term_memory": False, "tools": {"vision": False, "image_generation": False, "web": False, "voice": False, "local": False}},
        )

    def test_long_term_memory_is_distinct_and_disabled(self):
        memory = DisabledLongTermMemory()
        self.assertFalse(memory.available)
        self.assertEqual(memory.retrieve("anything"), [])

    def test_registry_rejects_client_paths_and_hides_local_path(self):
        registry = ModelRegistry({
            "approved": {"available": True, "display_name": "Approved", "local_path": "D:/secret"}
        })
        self.assertEqual(registry.available("approved")["local_path"], "D:/secret")
        with self.assertRaises(ValueError):
            registry.available("D:/arbitrary/model")
        self.assertNotIn("local_path", registry.public_models()[0])


if __name__ == "__main__":
    unittest.main()
