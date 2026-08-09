import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "training" / "scripts" / "convert_golden.py"
SPEC = importlib.util.spec_from_file_location("convert_golden", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_lossless_deterministic_conversion(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    manifest1 = tmp_path / "first.manifest.json"
    manifest2 = tmp_path / "second.manifest.json"
    golden_dir = ROOT / "dataset" / "golden"
    MODULE.convert(golden_dir, first, manifest1)
    MODULE.convert(golden_dir, second, manifest2)
    assert first.read_bytes() == second.read_bytes()
    rows = [json.loads(line) for line in first.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 200
    assert rows[0]["id"] == "shion_000101"
    assert rows[-1]["id"] == "shion_000300"
    assert sum(len(row["messages"]) > 2 for row in rows) == 121


def test_unicode_and_messages_are_preserved(tmp_path):
    output = tmp_path / "derived.jsonl"
    manifest = tmp_path / "manifest.json"
    MODULE.convert(ROOT / "dataset" / "golden", output, manifest)
    source = MODULE.load_golden(ROOT / "dataset" / "golden")[0]
    derived = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [r["messages"] for r in derived] == [r["messages"] for r in source]
    text = output.read_text(encoding="utf-8")
    for marker in ("♪", "♡", "〜", "（笑）", "\n"):
        assert marker in text

