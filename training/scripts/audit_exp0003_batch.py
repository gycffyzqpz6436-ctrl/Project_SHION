"""Deterministic static audit for Experiment 0003 candidate batches."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from training.scripts.audit_persona_coverage import assistant_text, assistant_turns, load_jsonl, percentile, sentence_count


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BATCH = ROOT / "dataset/candidates/jsonl/shion_candidates_batch_0005_exp0003_01.jsonl"
MANUAL_DENSITY_3 = {
    "shion_000301", "shion_000305", "shion_000310", "shion_000312", "shion_000314",
    "shion_000316", "shion_000317", "shion_000322", "shion_000326", "shion_000327",
    "shion_000328", "shion_000329", "shion_000330", "shion_000331", "shion_000333",
    "shion_000336", "shion_000338", "shion_000340",
}
MANUAL_DENSITY_1 = {"shion_000302", "shion_000313", "shion_000323", "shion_000324", "shion_000350"}
MANUAL_SEMANTIC_TEASING = {
    "shion_000301", "shion_000303", "shion_000305", "shion_000307", "shion_000309", "shion_000310",
    "shion_000312", "shion_000314", "shion_000316", "shion_000317", "shion_000320",
    "shion_000321", "shion_000322", "shion_000326", "shion_000327", "shion_000329",
    "shion_000330", "shion_000331", "shion_000333", "shion_000335", "shion_000336",
    "shion_000337", "shion_000338", "shion_000339", "shion_000340", "shion_000341",
    "shion_000342", "shion_000343", "shion_000344", "shion_000345", "shion_000347",
    "shion_000349",
}
GENERIC = re.compile(r"何か.{0,8}お手伝い|何か.{0,8}できること|遠慮なく言ってください|お役に立てれば|ご質問ありがとうございます|ご相談ください|いかがでしょうか|することをおすすめします")
ACTION_END = re.compile(r"(?:教えて|見せて|報告して|言ってね|やってみて|しておいで)[^\n。！？]*[。！？♪♡〜~]*$")


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def family(record: dict) -> str:
    number = int(record["id"].split("_")[-1])
    if number <= 325:
        return "minimal_everyday"
    if number <= 335:
        return "direct_affection"
    if number <= 343:
        return "semantic_teasing"
    return "technical_persona"


def density(record_id: str) -> int:
    if record_id in MANUAL_DENSITY_3:
        return 3
    if record_id in MANUAL_DENSITY_1:
        return 1
    return 2


def existing_records(batch_path: Path) -> list[dict]:
    paths = list((ROOT / "dataset/golden").glob("*.jsonl"))
    paths += [path for path in (ROOT / "dataset/candidates/jsonl").glob("*.jsonl") if path.resolve() != batch_path.resolve()]
    return [record for path in paths for record in load_jsonl(path)]


def audit_batch(records: list[dict], batch_path: Path = DEFAULT_BATCH) -> dict:
    old = existing_records(batch_path)
    prompts = [record["messages"][0]["content"] for record in records]
    responses = [assistant_text(record) for record in records]
    old_prompts = [(record["id"], record["messages"][0]["content"]) for record in old]
    old_responses = [(record["id"], assistant_text(record)) for record in old]
    exact_conversations = []
    old_conversations = {normalize(json.dumps(record["messages"], ensure_ascii=False)): record["id"] for record in old}
    for record in records:
        key = normalize(json.dumps(record["messages"], ensure_ascii=False))
        if key in old_conversations:
            exact_conversations.append([record["id"], old_conversations[key]])
    near = []
    for record, prompt, response in zip(records, prompts, responses):
        for old_id, old_prompt in old_prompts:
            ratio = SequenceMatcher(None, normalize(prompt), normalize(old_prompt)).ratio()
            if ratio >= .90 and normalize(prompt) != normalize(old_prompt):
                near.append({"candidate": record["id"], "existing": old_id, "kind": "prompt", "ratio": round(ratio, 3)})
        for old_id, old_response in old_responses:
            ratio = SequenceMatcher(None, normalize(response), normalize(old_response)).ratio()
            if ratio >= .88:
                near.append({"candidate": record["id"], "existing": old_id, "kind": "response", "ratio": round(ratio, 3)})
    turns = [turn for record in records for turn in assistant_turns(record)]
    lengths = [len(turn) for turn in turns]
    family_counts = Counter(family(record) for record in records)
    density_counts = Counter(density(record["id"]) for record in records)
    address_by_family = Counter()
    for record in records:
        if "お兄さん" in assistant_text(record):
            address_by_family[family(record)] += 1
    prompt_counts = Counter(normalize(prompt) for prompt in prompts)
    repeated_prompts = {
        prompt: [record["id"] for record in records if normalize(record["messages"][0]["content"]) == prompt]
        for prompt, count in prompt_counts.items() if count > 1
    }
    openings = Counter(re.split(r"[。！？!?\n]", response.strip(), maxsplit=1)[0] for response in responses)
    endings = Counter(
        parts[-2 if parts[-1] == "" else -1]
        for response in responses
        if (parts := re.split(r"[。！？!?\n]", response.strip()))
    )
    weakest_order = [
        "shion_000302", "shion_000313", "shion_000323", "shion_000324", "shion_000350",
        "shion_000304", "shion_000311", "shion_000318", "shion_000334", "shion_000348",
    ]
    return {
        "schema_version": 1,
        "candidate_count": len(records),
        "id_range": [records[0]["id"], records[-1]["id"]],
        "family_distribution": dict(family_counts),
        "category_distribution": dict(Counter(record["category"] for record in records)),
        "single_turn_count": sum("single_turn" in record["tags"] for record in records),
        "assistant_turn_count": len(turns),
        "one_or_two_sentence_turn_count": sum(sentence_count(turn) <= 2 for turn in turns),
        "response_length": {
            "min": min(lengths), "median": sorted(lengths)[len(lengths) // 2],
            "average": round(sum(lengths) / len(lengths), 2), "p75": percentile(lengths, .75),
            "p90": percentile(lengths, .90), "max": max(lengths),
        },
        "address": {
            "records": sum("お兄さん" in response for response in responses),
            "by_family": dict(address_by_family),
            "start": sum(any(turn.startswith("お兄さん") for turn in assistant_turns(record)) for record in records),
        },
        "semantic_teasing_count": sum(record["id"] in MANUAL_SEMANTIC_TEASING for record in records),
        "affection_count": family_counts["direct_affection"],
        "technical_persona_count": family_counts["technical_persona"],
        "surface_markers": {"music_note": sum(response.count("♪") for response in responses), "wave": sum(response.count("〜") for response in responses)},
        "question_ending_count": sum(bool(re.search(r"[？?](?:[♪♡〜~])?$", response.strip())) for response in responses),
        "action_request_ending_count": sum(bool(ACTION_END.search(response.strip())) for response in responses),
        "generic_assistant_count": sum(bool(GENERIC.search(response)) for response in responses),
        "exact_conversation_duplicates": exact_conversations,
        "near_duplicates": near,
        "repeated_prompts": repeated_prompts,
        "repeated_openings": {key: count for key, count in openings.items() if count > 1},
        "repeated_endings": {key: count for key, count in endings.items() if count > 1},
        "density_distribution": {str(score): density_counts[score] for score in range(4)},
        "strongest": [record["id"] for record in records if density(record["id"]) == 3][:10],
        "weakest": weakest_order,
    }


def render_review(records: list[dict], summary: dict) -> str:
    lines = [
        "# Experiment 0003 Expansion — Batch 1 Owner Review",
        "",
        "Status: Candidate / NOT GOLDEN / awaiting explicit Owner review",
        "",
        "This is a read-only review view of `shion_000301`–`shion_000350`. Density and teasing are",
        "manual semantic classifications encoded in the reproducible audit; they are not approval.",
        "",
        "| ID | Family | Category | Prompt | Response preview | Density | Address | Teasing | Chars |",
        "|---|---|---|---|---|---:|---|---|---:|",
    ]
    for record in records:
        prompt = record["messages"][0]["content"].replace("|", "/").replace("\n", " ")
        response = assistant_text(record).replace("|", "/").replace("\n", " ")
        preview = response[:96] + ("…" if len(response) > 96 else "")
        lines.append(
            f"| {record['id']} | {family(record)} | {record['category']} | {prompt} | {preview} | {density(record['id'])} | "
            f"{'Yes' if 'お兄さん' in response else 'No'} | "
            f"{'Yes' if record['id'] in MANUAL_SEMANTIC_TEASING else 'No'} | {len(response)} |"
        )
    lines += [
        "", "## Static summary", "", "```json",
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), "```", "",
        "Owner approval is required before any Golden or Database promotion. Batch 2 is blocked until then.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path, nargs="?", default=DEFAULT_BATCH)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--review-output", type=Path)
    args = parser.parse_args()
    records = load_jsonl(args.batch)
    summary = audit_batch(records, args.batch)
    if args.review_output:
        args.review_output.write_text(render_review(records, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))


if __name__ == "__main__":
    main()
