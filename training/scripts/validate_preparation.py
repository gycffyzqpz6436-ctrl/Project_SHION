"""Validate fixed evaluation and its isolation from Golden prompts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REQUIRED = {"eval_id", "category", "scenario", "user_prompt", "expected_traits", "forbidden_failure_modes"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", type=Path, default=Path("training/eval/shion_sft_exp_0001_eval.jsonl"))
    parser.add_argument("--golden-dir", type=Path, default=Path("dataset/golden"))
    args = parser.parse_args()
    evaluation = load_jsonl(args.eval)
    golden = [item for p in sorted(args.golden_dir.glob("*.jsonl")) for item in load_jsonl(p)]
    errors: list[str] = []
    ids = [item.get("eval_id") for item in evaluation]
    prompts = [item.get("user_prompt") for item in evaluation]
    golden_text = {m["content"] for item in golden for m in item["messages"]}
    for index, item in enumerate(evaluation, 1):
        if set(item) != REQUIRED:
            errors.append(f"line {index}: fields differ from required schema")
        if not isinstance(item.get("expected_traits"), list) or not item["expected_traits"]:
            errors.append(f"line {index}: expected_traits must be non-empty")
        if not isinstance(item.get("forbidden_failure_modes"), list) or not item["forbidden_failure_modes"]:
            errors.append(f"line {index}: forbidden_failure_modes must be non-empty")
    if len(evaluation) < 30:
        errors.append("evaluation has fewer than 30 records")
    if len(ids) != len(set(ids)):
        errors.append("duplicate eval_id")
    if len(prompts) != len(set(prompts)):
        errors.append("duplicate evaluation prompt")
    copied = sorted(set(prompts) & golden_text)
    if copied:
        errors.append(f"evaluation prompts copied verbatim from Golden: {copied}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {len(evaluation)} evaluations; categories={dict(sorted(Counter(i['category'] for i in evaluation).items()))}")


if __name__ == "__main__":
    main()

