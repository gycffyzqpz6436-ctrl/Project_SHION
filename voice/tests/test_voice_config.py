import json
import unittest
from pathlib import Path, PureWindowsPath


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
CONFIGS = [CONFIG_DIR / "prototype_v0_1.json", CONFIG_DIR / "prototype_v0_1_f2.json"]


class VoiceConfigTests(unittest.TestCase):
    def test_all_large_paths_are_under_external_root(self) -> None:
        for config_path in CONFIGS:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            root = PureWindowsPath(config["external_root"])
            paths = [
                PureWindowsPath(config["runtime_source"]),
                PureWindowsPath(config["python"]),
                PureWindowsPath(config["output_dir"]),
                *(PureWindowsPath(value) for value in config["model"].values() if isinstance(value, str) and ":\\" in value),
            ]
            for path in paths:
                self.assertTrue(path.is_relative_to(root), path)

    def test_cuda_is_explicit(self) -> None:
        for config_path in CONFIGS:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["generation"]["device"], "cuda")


if __name__ == "__main__":
    unittest.main()
