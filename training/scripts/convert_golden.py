"""Convert only Owner-approved Golden records to lossless, template-neutral SFT JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_golden(directory: Path) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    sources: list[dict] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.jsonl")):
        sources.append({"path": path.as_posix(), "sha256": sha256_file(path)})
        with path.open(encoding="utf-8", newline="") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    raise ValueError(f"{path}:{line_number}: blank line")
                record = json.loads(line)
                record_id = record.get("id")
                if record.get("status") != "golden":
                    raise ValueError(f"{record_id}: non-Golden source record")
                review = record.get("review", {})
                if review.get("owner_approved") is not True or review.get("result") != "pass":
                    raise ValueError(f"{record_id}: missing Owner approval")
                if record_id in seen:
                    raise ValueError(f"{record_id}: duplicate Golden id")
                messages = record.get("messages")
                if not isinstance(messages, list) or len(messages) < 2:
                    raise ValueError(f"{record_id}: invalid messages")
                if any(m.get("role") != ("user" if i % 2 == 0 else "assistant") for i, m in enumerate(messages)):
                    raise ValueError(f"{record_id}: role alternation failure")
                if messages[-1].get("role") != "assistant":
                    raise ValueError(f"{record_id}: final role is not assistant")
                seen.add(record_id)
                records.append({
                    "id": record_id,
                    "revision": record["revision"],
                    "category": record["category"],
                    "messages": messages,
                })
    records.sort(key=lambda item: item["id"])
    return records, sources


def write_jsonl(records: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def convert(golden_dir: Path, output: Path, manifest: Path) -> None:
    records, sources = load_golden(golden_dir)
    write_jsonl(records, output)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": "shion_sft_exp_0001",
        "source_golden_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
        ).strip(),
        "record_count": len(records),
        "golden_ids": [r["id"] for r in records],
        "sources": sources,
        "dataset_sha256": hashlib.sha256(
            b"".join(Path(item["path"]).read_bytes() for item in sources)
        ).hexdigest(),
        "conversion_script_sha256": sha256_file(Path(__file__)),
        "derived_sha256": sha256_file(output),
        "format": "template-neutral messages JSONL",
    }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    convert(args.golden_dir, args.output, args.manifest)


if __name__ == "__main__":
    main()
