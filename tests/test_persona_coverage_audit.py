import json
from pathlib import Path

from training.scripts.audit_persona_coverage import (
    audit,
    load_golden,
    normalized_ending,
    percentile,
)


ROOT = Path(__file__).resolve().parents[1]


def test_formal_golden_range_and_database_lineage_are_exact():
    records = load_golden()
    result = audit(records)
    assert result["record_count"] == 200
    assert result["id_range"] == ["shion_000101", "shion_000300"]
    assert result["database_lineage_match"] is True


def test_counting_is_deterministic_and_schema_is_stable():
    records = load_golden()
    first, second = audit(records), audit(records)
    assert first == second
    required = {
        "record_count", "address", "assistant_bias", "style_distribution",
        "record_characters", "density_distribution", "records",
    }
    assert required <= first.keys()
    assert len(first["records"]) == 200


def test_phrase_normalization_and_percentile():
    assert normalized_ending("うん。\nまた話してね〜♪") == "また話してね"
    assert percentile([1, 2, 3, 4, 5], .75) == 4


def test_audit_never_writes_or_rewrites_golden(tmp_path):
    paths = sorted((ROOT / "dataset" / "golden").glob("*.jsonl"))
    before = {path: path.read_bytes() for path in paths}
    audit(load_golden())
    after = {path: path.read_bytes() for path in paths}
    assert before == after


def test_cli_payload_is_json_serializable():
    json.dumps(audit(load_golden()), ensure_ascii=False, sort_keys=True)
