import json
from pathlib import Path

from training.scripts.audit_exp0003_batch import (
    MANUAL_SEMANTIC_TEASING,
    audit_batch,
    render_review,
)
from training.scripts.audit_persona_coverage import load_jsonl


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "dataset/candidates/jsonl/shion_candidates_batch_0005_exp0003_01.jsonl"


def records():
    return load_jsonl(BATCH)


def test_candidate_identity_and_review_gate():
    data = records()
    assert len(data) == 50
    assert [item["id"] for item in data] == [f"shion_{number:06d}" for number in range(301, 351)]
    assert all(item["revision"] == 1 and item["status"] == "candidate" for item in data)
    assert all(item["review"]["owner_approved"] is False for item in data)
    assert all(item["review"]["result"] is None for item in data)


def test_batch_quota_and_static_quality_targets():
    summary = audit_batch(records(), BATCH)
    assert summary["family_distribution"] == {
        "minimal_everyday": 25,
        "direct_affection": 10,
        "semantic_teasing": 8,
        "technical_persona": 7,
    }
    assert summary["single_turn_count"] == 42
    assert summary["assistant_turn_count"] == 58
    assert summary["one_or_two_sentence_turn_count"] == 58
    assert summary["address"]["records"] == 37
    assert summary["address"]["by_family"] == {
        "minimal_everyday": 18,
        "direct_affection": 9,
        "semantic_teasing": 6,
        "technical_persona": 4,
    }
    assert summary["density_distribution"] == {"0": 0, "1": 5, "2": 27, "3": 18}
    assert summary["generic_assistant_count"] == 0
    assert summary["action_request_ending_count"] == 0
    assert summary["surface_markers"] == {"music_note": 5, "wave": 5}
    assert summary["exact_conversation_duplicates"] == []
    assert summary["near_duplicates"] == []


def test_mandatory_prompts_and_semantic_teasing_metadata():
    data = records()
    prompts = {item["messages"][0]["content"] for item in data}
    mandatory = {
        "こんにちは", "おはよ", "おやすみ", "ただいま", "疲れた", "今日仕事疲れた〜",
        "眠い", "暇", "今日何もしなかった", "仕事行きたくない", "甘やかして",
        "ちょっと甘やかして", "癒して", "褒めて", "構って",
        "ポート3000使ってるプロセス確認したい",
    }
    assert mandatory <= prompts
    tagged = {item["id"] for item in data if "teasing_light" in item["tags"]}
    assert tagged <= MANUAL_SEMANTIC_TEASING


def test_owner_review_is_complete_and_serializable():
    data = records()
    summary = audit_batch(data, BATCH)
    rendered = render_review(data, summary)
    assert rendered.count("| shion_") == 50
    assert "NOT GOLDEN" in rendered
    json.dumps(summary, ensure_ascii=False)
