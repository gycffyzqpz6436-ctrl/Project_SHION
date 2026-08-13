from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np

from voice_runtime import DEFAULT_CONFIG, configure_external_environment, load_config, validate_external_paths


def write_wav(path: Path, sample_rate: int, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.asarray(audio, dtype=np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one local Japanese WAV with Style-Bert-VITS2.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warm-output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    configure_external_environment(config)
    validate_external_paths(config)

    import torch
    from style_bert_vits2.constants import Languages
    from style_bert_vits2.tts_model import TTSModel

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available; refusing CPU fallback")
    model_config = config["model"]
    generation = config["generation"]
    process_started = time.perf_counter()
    model = TTSModel(
        model_path=Path(model_config["checkpoint"]),
        config_path=Path(model_config["config"]),
        style_vec_path=Path(model_config["style_vectors"]),
        device=generation["device"],
    )

    def generate(output: Path) -> dict[str, float | int | str]:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        started = time.perf_counter()
        sample_rate, audio = model.infer(
            text=args.text,
            language=Languages.JP,
            style=generation["style"],
            style_weight=generation["style_weight"],
            length=generation["length"],
            pitch_scale=generation["pitch_scale"],
            intonation_scale=generation["intonation_scale"],
            sdp_ratio=generation["sdp_ratio"],
            noise=generation["noise"],
            noise_w=generation["noise_w"],
            line_split=False,
        )
        torch.cuda.synchronize()
        latency = time.perf_counter() - started
        write_wav(output, sample_rate, audio)
        return {
            "path": str(output.resolve()),
            "latency_seconds": round(latency, 4),
            "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2),
            "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 2),
            "wav_duration_seconds": round(len(audio) / sample_rate, 4),
            "sample_rate_hz": sample_rate,
            "samples": len(audio),
            "file_size_bytes": output.stat().st_size,
        }

    first = generate(args.output)
    warm = generate(args.warm_output) if args.warm_output else None
    report = {
        "text": args.text,
        "model": model_config["name"],
        "style": generation["style"],
        "style_weight": generation["style_weight"],
        "process_elapsed_seconds": round(time.perf_counter() - process_started, 4),
        "first_run": first,
        "warm_run": warm,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
