import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "training" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def import_script(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_configs_and_prompt_modes():
    prompt_utils = import_script("prompt_utils")
    common = yaml.safe_load((ROOT / "training/configs/common.yaml").read_text(encoding="utf-8"))
    primary = yaml.safe_load((ROOT / "training/configs/shion_sft_exp_0001_ministral8b.yaml").read_text(encoding="utf-8"))
    assert common["training_system_prompt_mode"] == "none"
    assert common["evaluation_modes"] == ["canonical", "minimal"]
    assert primary["model_id"].startswith("mistralai/")
    prompt = prompt_utils.system_prompt_for_mode("canonical", ROOT / common["canonical_system_prompt"])
    assert prompt.startswith("You are SHION.")
    assert "Synchronization Workflow" not in prompt
    assert prompt_utils.system_prompt_for_mode("minimal", ROOT / common["canonical_system_prompt"]) is None


def test_all_records_have_exact_assistant_mask():
    transformers = pytest.importorskip("transformers")
    train_sft = import_script("train_sft")
    model_path = Path(r"D:\AI\Project_SHION\models\mistral\ministral-3-8b-instruct-2512-bf16")
    if not model_path.exists():
        pytest.skip("official local model is not present")
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False, fix_mistral_regex=True
    )
    data = ROOT / "training/data/generated/shion_sft_exp_0001.jsonl"
    if not data.exists():
        pytest.skip("generated training artifact is not present")
    rows = [json.loads(line) for line in data.read_text(encoding="utf-8").splitlines()]
    encoded = [train_sft.tokenize_assistant_only(tokenizer, row["messages"], 2048) for row in rows]
    assert len(encoded) == 200
    assert max(len(row["input_ids"]) for row in encoded) == 835
    assert all(any(label != -100 for label in row["labels"]) for row in encoded)


def test_baseline_resume_prefix_validation(tmp_path):
    baseline = import_script("run_baseline")
    evaluations = [
        {"eval_id": "shion_eval_0001", "user_prompt": "prompt one"},
        {"eval_id": "shion_eval_0002", "user_prompt": "prompt two"},
    ]
    partial = tmp_path / "baseline.jsonl.partial"
    prompt_hash = baseline.sha256_bytes(b"prompt one")
    partial.write_text(
        json.dumps({
            "eval_id": "shion_eval_0001",
            "mode": "canonical",
            "prompt_sha256": prompt_hash,
            "response": "response",
        }) + "\n",
        encoding="utf-8",
    )
    rows = baseline.load_resume_prefix(partial, evaluations, "canonical")
    assert len(rows) == 1
    with pytest.raises(ValueError):
        baseline.load_resume_prefix(partial, evaluations, "minimal")


def test_baseline_metadata_is_fully_pinned():
    baseline = import_script("run_baseline")
    common = yaml.safe_load((ROOT / "training/configs/common.yaml").read_text(encoding="utf-8"))
    primary = yaml.safe_load((ROOT / "training/configs/shion_sft_exp_0001_ministral8b.yaml").read_text(encoding="utf-8"))
    model_path = Path(primary["model_path"])
    if not model_path.exists():
        pytest.skip("official local model is not present")
    transformers = pytest.importorskip("transformers")
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False, fix_mistral_regex=True
    )
    metadata = baseline.build_metadata(
        common,
        primary,
        "canonical",
        ROOT / common["evaluation_data"],
        ROOT / common["canonical_system_prompt"],
        tokenizer,
    )
    assert metadata["model_revision"] == "f6fae9795746f63c9be8344932f01275f3c63734"
    assert metadata["evaluation_count"] == 36
    assert metadata["adapter"] is None
    assert metadata["trust_remote_code"] is False
    assert metadata["local_files_only"] is True
    assert metadata["effective_system_prompt_sha256"]
