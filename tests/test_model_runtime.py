import json
import unittest
from pathlib import Path

import torch

from app.runtime.model_runtime import RepeatedSequenceStoppingCriteria


ROOT = Path(__file__).resolve().parents[1]


class RepetitionGuardTests(unittest.TestCase):
    def test_stops_three_consecutive_repeated_blocks(self):
        guard = RepeatedSequenceStoppingCriteria(prompt_length=2, min_block_tokens=4, max_block_tokens=8, repeats=3)
        ids = torch.tensor([[1, 2, 10, 11, 12, 13, 10, 11, 12, 13, 10, 11, 12, 13]])
        self.assertTrue(guard(ids, torch.empty(0)))
        self.assertTrue(guard.triggered)

    def test_does_not_stop_ordinary_nonconsecutive_repetition(self):
        guard = RepeatedSequenceStoppingCriteria(prompt_length=2, min_block_tokens=4, max_block_tokens=8, repeats=3)
        ids = torch.tensor([[1, 2, 10, 11, 12, 13, 20, 10, 11, 12, 13]])
        self.assertFalse(guard(ids, torch.empty(0)))

    def test_generation_override_is_impish_only(self):
        registry = json.loads((ROOT / "app" / "model_registry.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["impish_nemo12b_experimental"]["generation_overrides"]["max_new_tokens"], 128)
        self.assertIn("repetition_guard", registry["impish_nemo12b_experimental"])
        self.assertFalse(registry["impish_nemo12b_experimental"]["available"])
        self.assertNotIn("shisa_v2_nemo12b_experimental", registry)
        self.assertNotIn("generation_overrides", registry["ministral3_official"])
        self.assertNotIn("generation_overrides", registry["nemo12b_official"])


if __name__ == "__main__":
    unittest.main()
