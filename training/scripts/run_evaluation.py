"""Create or merge deterministic evaluation result artifacts without downloading models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a human-review comparison artifact")
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--baseline-responses", type=Path)
    parser.add_argument("--finetuned-responses", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluation = load(args.eval)
    baseline = {r["eval_id"]: r["response"] for r in load(args.baseline_responses)} if args.baseline_responses else {}
    finetuned = {r["eval_id"]: r["response"] for r in load(args.finetuned_responses)} if args.finetuned_responses else {}
    axes = ["shion_identity", "naturalness", "relationship_distance", "teasing_quality", "affection_quality", "emotional_presence", "technical_accuracy", "serious_voice_continuity", "safety_accuracy", "safety_voice_continuity", "phrase_overfitting", "structural_repetition"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for item in evaluation:
            eid = item["eval_id"]
            result = {
                **item,
                "baseline_response": baseline.get(eid),
                "finetuned_response": finetuned.get(eid),
                "human_review": None,
                "score": {axis: None for axis in axes},
            }
            handle.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()

