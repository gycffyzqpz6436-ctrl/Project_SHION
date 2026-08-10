from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


REPO_ID = "cagliostrolab/animagine-xl-4.0"
REVISION = "2b7c1b397761bf5bd3cc42e5b39ec99314a75a96"
WEIGHT = "animagine-xl-4.0-opt.safetensors"
MIN_REMAINING_BYTES = 80 * 1024**3


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    destination = args.destination.resolve()

    free_before = shutil.disk_usage(destination.anchor).free
    if free_before < MIN_REMAINING_BYTES + 16 * 1024**3:
        raise SystemExit("insufficient capacity: download would violate the 80 GiB reserve")

    api = HfApi()
    info = api.model_info(REPO_ID, revision=REVISION, files_metadata=True)
    if info.gated:
        raise SystemExit("refusing gated repository")
    unsafe = [
        f.rfilename
        for f in info.siblings
        if Path(f.rfilename).suffix.lower() in {".ckpt", ".pkl", ".pickle", ".exe", ".dll", ".bat", ".cmd"}
    ]
    if unsafe:
        raise SystemExit(f"refusing unexpected unsafe files: {unsafe}")

    snapshot_download(
        repo_id=REPO_ID,
        revision=REVISION,
        local_dir=destination,
        allow_patterns=[
            "README.md",
            "model_index.json",
            "scheduler/*",
            "text_encoder/*",
            "text_encoder_2/*",
            "tokenizer/*",
            "tokenizer_2/*",
            "unet/*.json",
            "vae/*",
            WEIGHT,
        ],
    )
    weight_path = destination / WEIGHT
    record = {
        "repository": REPO_ID,
        "revision": REVISION,
        "weight": WEIGHT,
        "size_bytes": weight_path.stat().st_size,
        "sha256": sha256(weight_path),
        "hf_blob_id": next(f.blob_id for f in info.siblings if f.rfilename == WEIGHT),
        "hf_lfs": next(f.lfs for f in info.siblings if f.rfilename == WEIGHT),
        "free_before_bytes": free_before,
        "free_after_bytes": shutil.disk_usage(destination.anchor).free,
    }
    (destination / "SHION_INTEGRITY.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
