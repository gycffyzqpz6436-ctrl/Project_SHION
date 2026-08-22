import json
from pathlib import Path

import pytest
import yaml

from training.scripts.run_exp0002_manual import (
    LAUNCH_STEPS,
    atomic_json,
    build_parser,
    disk_guard,
    full_approval_guard,
    make_run_dir,
    nvidia_sample,
    static_preflight,
    validate_config,
)


CONFIG = Path("training/configs/shion_sft_exp_0002_gemma4.yaml")


def test_launch_gate_hard_limit_and_precision_policy():
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    validate_config(config, mode="launch")
    assert LAUNCH_STEPS == config["guards"]["launch_max_optimizer_steps"] == 5
    assert "prepare_gemma4_for_kbit_training_precision_aware" in config["precision"]["helper"]


def test_full_training_requires_distinct_approval_flag():
    with pytest.raises(SystemExit, match="Refusing Full Training"):
        full_approval_guard("full", False)
    full_approval_guard("full", True)
    full_approval_guard("launch", False)


def test_static_preflight_loads_exact_dataset_without_gpu():
    result = static_preflight(CONFIG, mode="launch")
    assert result["record_count"] == 200
    assert result["dataset_sha256"] == "3111b8e1358692434c3f1b7db0e6376bbb6eee28d709c61a8b6e4e4674da4b9f"


def test_unsafe_step_limit_is_rejected():
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    config["guards"]["launch_max_optimizer_steps"] = 6
    with pytest.raises(ValueError, match="hard limit"):
        validate_config(config, mode="launch")


def test_cli_separates_launch_full_reload_and_validate():
    parser = build_parser()
    assert parser.parse_args(["launch", "--config", str(CONFIG)]).command == "launch"
    full = parser.parse_args(["full", "--config", str(CONFIG)])
    assert full.command == "full" and not full.owner_approved_full_training
    assert parser.parse_args(["reload", "--manifest", "manifest.json"]).command == "reload"
    assert parser.parse_args(["validate", "--config", str(CONFIG)]).command == "validate"


def test_manifest_schema_fields_are_json_serializable():
    sample = {"schema_version": 1, "status": "RUNNING", "mode": "launch", "max_optimizer_steps": 5, "dataset_sha256": "a" * 64, "model_revision": "b" * 40, "adapter_path": None}
    assert json.loads(json.dumps(sample))["max_optimizer_steps"] == 5


def test_output_path_is_timestamped_under_launch_root(tmp_path):
    config = {"output_root": str(tmp_path)}
    run_dir = make_run_dir(config, "launch", None)
    assert run_dir.parent == tmp_path / "launch_gate"
    assert run_dir.name.startswith("run-")


def test_resume_requires_checkpoint_directory(tmp_path):
    invalid = tmp_path / "not-a-checkpoint"
    invalid.mkdir()
    with pytest.raises(ValueError, match="checkpoint"):
        make_run_dir({"output_root": str(tmp_path)}, "full", invalid)


def test_disk_guard_refuses_impossible_threshold(tmp_path):
    with pytest.raises(RuntimeError, match="insufficient disk"):
        disk_guard(tmp_path, 10**9)


def test_monitoring_failure_is_separate_from_training_failure(monkeypatch):
    monkeypatch.setattr("subprocess.check_output", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline monitor")))
    assert "monitoring_error" in nvidia_sample(strict=False)


def test_atomic_json_replaces_temporary_file(tmp_path):
    path = tmp_path / "metrics.json"
    atomic_json(path, {"status": "FAIL", "error": {"type": "Synthetic"}})
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "FAIL"
    assert not path.with_suffix(".json.tmp").exists()
