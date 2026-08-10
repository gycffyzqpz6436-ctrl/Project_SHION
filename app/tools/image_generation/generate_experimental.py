from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

# Force hub clients offline before importing the ML stack.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("DIFFUSERS_OFFLINE", "1")

import torch
from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline

from app.tools.image_generation.prompt_builder import build_animagine_prompt
from app.tools.image_generation.spec import ShionVisualSpec


def gpu_sample() -> dict[str, str]:
    command = [
        "nvidia-smi",
        "--query-gpu=memory.used,memory.total,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    values = subprocess.check_output(command, text=True).strip().split(", ")
    return dict(zip(("used_mib", "total_mib", "temperature_c", "power_w"), values))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded offline SHION model test")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pose", default="simple full-body standing pose")
    parser.add_argument("--seed", type=int, default=20260810)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    spec = ShionVisualSpec(
        subject="beautiful woman with long violet hair and violet eyes",
        appearance=("natural face", "correct anatomy", "balanced body proportions"),
        clothing=("elegant navy tailored dress", "high heels"),
        expression="gentle confident smile",
        pose=args.pose,
        background="minimal pale studio background",
        lighting="soft clean studio lighting",
        hands_visible=True,
    )
    prompt, negative_prompt = build_animagine_prompt(spec)
    weight = args.model_dir / "animagine-xl-4.0-opt.safetensors"

    before = gpu_sample()
    load_start = time.perf_counter()
    pipe = StableDiffusionXLPipeline.from_single_file(
        str(weight),
        config=str(args.model_dir),
        torch_dtype=torch.float16,
        use_safetensors=True,
        local_files_only=True,
    )
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.vae.enable_slicing()
    pipe.to("cuda")
    load_seconds = time.perf_counter() - load_start

    torch.cuda.reset_peak_memory_stats()
    generate_start = time.perf_counter()
    image = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=1024,
        height=1024,
        num_inference_steps=28,
        guidance_scale=5.0,
        generator=torch.Generator(device="cuda").manual_seed(args.seed),
    ).images[0]
    torch.cuda.synchronize()
    generation_seconds = time.perf_counter() - generate_start
    peak_allocated = torch.cuda.max_memory_allocated()
    peak_reserved = torch.cuda.max_memory_reserved()
    after = gpu_sample()
    image.save(args.output)

    record = {
        "offline": True,
        "trust_remote_code": False,
        "resolution": [1024, 1024],
        "steps": 28,
        "scheduler": type(pipe.scheduler).__name__,
        "cfg": 5.0,
        "seed": args.seed,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "model_load_seconds": round(load_seconds, 3),
        "generation_seconds": round(generation_seconds, 3),
        "torch_peak_allocated_bytes": peak_allocated,
        "torch_peak_reserved_bytes": peak_reserved,
        "gpu_before": before,
        "gpu_after": after,
        "output": str(args.output.resolve()),
        "output_size_bytes": args.output.stat().st_size,
    }
    metrics = args.output.with_suffix(".json")
    metrics.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
