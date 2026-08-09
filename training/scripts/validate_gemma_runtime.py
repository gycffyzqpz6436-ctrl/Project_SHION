"""Short, offline Gemma 4 runtime gate; never writes generated responses."""

from __future__ import annotations

import gc
import json
import subprocess
import threading
import time
from pathlib import Path

import torch
from transformers import AutoModelForMultimodalLM, AutoTokenizer, BitsAndBytesConfig, set_seed


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(r"D:\AI\Project_SHION\models\experimental\gemma-4-12b-it")
PROMPTS = (
    "こんにちは",
    "今日仕事疲れた〜",
    "お菓子3個までなのに5個買っちゃった",
    "ぽすん。",
    "今日は何もしない日にする",
)


def final_channel(tokenizer, token_ids: torch.Tensor) -> tuple[str, str]:
    """Return displayable final text and the raw channel-formatted decode."""
    raw = tokenizer.decode(token_ids, skip_special_tokens=False).strip()
    marker = "<|channel>final\n"
    if marker in raw:
        display = raw.rsplit(marker, 1)[1].split("<channel|>", 1)[0].strip()
    else:
        display = tokenizer.decode(token_ids, skip_special_tokens=True).strip()
    return display, raw


def main() -> None:
    neutral = (ROOT / "app/prompts/neutral_conversation.txt").read_text(encoding="utf-8").strip()
    telemetry: list[dict] = []
    stopped = threading.Event()

    def monitor() -> None:
        while not stopped.is_set():
            try:
                raw = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=memory.used,temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
                    text=True,
                ).strip().split(",")
                telemetry.append({"used_mib": float(raw[0]), "temp_c": float(raw[1]), "power_w": float(raw[2])})
            except Exception:
                pass
            stopped.wait(0.5)

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    load_started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, local_files_only=True, trust_remote_code=False)
    model = AutoModelForMultimodalLM.from_pretrained(
        MODEL_PATH,
        local_files_only=True,
        trust_remote_code=False,
        quantization_config=quantization,
        device_map="auto",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    ).eval()
    load_seconds = time.perf_counter() - load_started
    results = []
    for mode in ("minimal", "neutral"):
        for index, prompt in enumerate(PROMPTS):
            messages = [{"role": "user", "content": prompt}]
            if mode == "neutral":
                messages.insert(0, {"role": "system", "content": neutral})
            batch = tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
                enable_thinking=False,
            ).to(model.device)
            set_seed(20260809 + index + (100 if mode == "neutral" else 0))
            generation_started = time.perf_counter()
            with torch.inference_mode():
                output = model.generate(
                    **batch,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.8,
                    top_k=20,
                    repetition_penalty=1.1,
                    max_new_tokens=96,
                    eos_token_id=model.generation_config.eos_token_id,
                    pad_token_id=tokenizer.pad_token_id,
                    use_cache=True,
                )
            new_tokens = output[0, batch["input_ids"].shape[1] :]
            response, raw = final_channel(tokenizer, new_tokens)
            result = {
                "mode": mode,
                "prompt": prompt,
                "response": response,
                "new_tokens": int(new_tokens.shape[0]),
                "seconds": round(time.perf_counter() - generation_started, 3),
                "raw_has_thought_channel": "<|channel>thought" in raw,
                "raw_has_final_channel": "<|channel>final" in raw,
            }
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            del batch, output, new_tokens

    summary = {
        "model_class": type(model).__name__,
        "load_seconds": round(load_seconds, 3),
        "allocated_mib": round(torch.cuda.memory_allocated() / 1024**2),
        "reserved_mib": round(torch.cuda.memory_reserved() / 1024**2),
        "torch_peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2),
        "total_seconds_before_release": round(time.perf_counter() - started, 3),
        "results": results,
    }
    del model, tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    time.sleep(2)
    summary["after_release_allocated_mib"] = round(torch.cuda.memory_allocated() / 1024**2)
    summary["after_release_reserved_mib"] = round(torch.cuda.memory_reserved() / 1024**2)
    stopped.set()
    monitor_thread.join(timeout=2)
    summary["nvidia_peak_used_mib"] = round(max((row["used_mib"] for row in telemetry), default=0))
    summary["max_temp_c"] = max((row["temp_c"] for row in telemetry), default=0)
    summary["max_power_w"] = max((row["power_w"] for row in telemetry), default=0)
    print("RUNTIME_SUMMARY=" + json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
