from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

from voice_runtime import DEFAULT_CONFIG, configure_external_environment, load_config, validate_external_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose the isolated Voice Prototype runtime.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    configure_external_environment(config)
    validate_external_paths(config)

    import torch
    import torchaudio
    from style_bert_vits2.constants import VERSION
    from style_bert_vits2.tts_model import TTSModel  # noqa: F401

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available in the isolated voice runtime")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    left = torch.randn((1024, 1024), device="cuda", dtype=torch.float16)
    right = torch.randn((1024, 1024), device="cuda", dtype=torch.float16)
    started = time.perf_counter()
    result = left @ right
    torch.cuda.synchronize()
    report = {
        "python": platform.python_version(),
        "style_bert_vits2": VERSION,
        "torch": torch.__version__,
        "torchaudio": torchaudio.__version__,
        "compiled_cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "compute_capability": list(torch.cuda.get_device_capability(0)),
        "cuda_arch_list": torch.cuda.get_arch_list(),
        "kernel_seconds": round(time.perf_counter() - started, 6),
        "kernel_result_finite": bool(torch.isfinite(result).all()),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2),
        "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 2),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
