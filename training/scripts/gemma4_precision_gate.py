"""Bounded current-versus-precision-aware Gemma 4 k-bit preparation Gate."""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import torch
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoConfig, AutoTokenizer, BitsAndBytesConfig, Gemma4UnifiedForCausalLM

from training.scripts.gemma4_feasibility import NvidiaMonitor, choose_smoke_records, cuda_metrics, is_text_decoder_target, load_jsonl, lora_leaf_modules, make_batch
from training.scripts.kbit_precision import prepare_gemma4_for_kbit_training_precision_aware
from training.scripts.train_sft import tokenize_assistant_only


MIB = 1024**2


def category_for_parameter(name: str, parameter: torch.Tensor) -> str:
    lowered = name.lower()
    if parameter.__class__.__name__ == "Params4bit":
        return "quantized_linear4bit"
    if "embed_tokens" in lowered or "embedding" in lowered:
        return "embedding"
    if "lm_head" in lowered:
        return "lm_head"
    if "norm" in lowered:
        return "norm"
    if "self_attn" in lowered:
        return "attention_non_quantized"
    if ".mlp." in lowered:
        return "mlp_non_quantized"
    return "other"


def parameter_inventory(model: Any) -> dict[str, Any]:
    by_dtype: dict[str, dict[str, int]] = defaultdict(lambda: {"tensors": 0, "elements": 0, "bytes": 0})
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"tensors": 0, "elements": 0, "bytes": 0})
    for name, parameter in model.named_parameters():
        size = parameter.numel() * parameter.element_size()
        for bucket, key in ((by_dtype, str(parameter.dtype)), (by_category, category_for_parameter(name, parameter))):
            bucket[key]["tensors"] += 1
            bucket[key]["elements"] += parameter.numel()
            bucket[key]["bytes"] += size
    return {"by_dtype": dict(by_dtype), "by_category": dict(by_category)}


def grad_report(model: Any) -> dict[str, Any]:
    squared = 0.0
    count = 0
    finite = True
    frozen_gradients: list[str] = []
    for name, parameter in model.named_parameters():
        if parameter.grad is not None:
            if not parameter.requires_grad:
                frozen_gradients.append(name)
                continue
            count += 1
            finite = finite and bool(torch.isfinite(parameter.grad).all())
            squared += float(parameter.grad.detach().float().pow(2).sum().cpu())
    return {
        "trainable_gradient_tensors": count,
        "all_finite": finite,
        "global_norm": math.sqrt(squared),
        "frozen_gradient_names": frozen_gradients,
    }


def load_base(model_path: Path, quantization: BitsAndBytesConfig) -> tuple[Any, dict[str, Any]]:
    config = AutoConfig.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    return Gemma4UnifiedForCausalLM.from_pretrained(
        model_path,
        config=config.text_config,
        local_files_only=True,
        trust_remote_code=False,
        key_mapping={r"^model\.language_model\.": "model."},
        output_loading_info=True,
        quantization_config=quantization,
        device_map={"": 0},
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("current", "precision"), required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--owner-approved-precision-gate", action="store_true")
    args = parser.parse_args()
    if not args.owner_approved_precision_gate:
        raise SystemExit("Refusing GPU Gate without --owner-approved-precision-gate")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = args.output_dir / "adapter"
    result_path = args.output_dir / "precision_gate.json"
    result: dict[str, Any] = {"status": "FAIL", "mode": args.mode, "seed": 42, "stages": {}, "errors": []}
    monitor = NvidiaMonitor()
    model = optimizer = tokenizer = batch = output = loss = base = reloaded = None

    def stage(name: str, **extra: Any) -> None:
        torch.cuda.synchronize()
        result["stages"][name] = {**cuda_metrics(), "nvidia": NvidiaMonitor.sample(), **extra}

    monitor.start()
    try:
        torch.manual_seed(42)
        torch.cuda.manual_seed_all(42)
        tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True, trust_remote_code=False)
        rows = load_jsonl(args.data)
        encoded = {row["id"]: tokenize_assistant_only(tokenizer, row["messages"], 512) for row in rows}
        lengths = {key: len(value["input_ids"]) for key, value in encoded.items()}
        if len(rows) != 200 or max(lengths.values()) != 290 or any(length > 512 for length in lengths.values()):
            raise RuntimeError("Dataset count/length invariant failed")
        longest = next(row for row in rows if row["id"] == "shion_000191")
        smoke = choose_smoke_records(rows, lengths)
        result["records"] = {"longest": [longest["id"], lengths[longest["id"]]], "smoke": [[row["id"], lengths[row["id"]]] for row in smoke]}

        quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
        torch.cuda.reset_peak_memory_stats()
        model, loading_info = load_base(args.model_path, quantization)
        input_weight = model.get_input_embeddings().weight
        output_weight = model.get_output_embeddings().weight
        tied_pointer = input_weight.data_ptr()
        stage("base", inventory=parameter_inventory(model), tied=input_weight is output_weight and input_weight.data_ptr() == output_weight.data_ptr(), unexpected_keys=sorted(loading_info["unexpected_keys"]))

        if args.mode == "current":
            model.config.use_cache = False
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False})
        else:
            model = prepare_gemma4_for_kbit_training_precision_aware(model, gradient_checkpointing_kwargs={"use_reentrant": False})
        stage("prepared", inventory=parameter_inventory(model), tied=model.get_input_embeddings().weight.data_ptr() == tied_pointer == model.get_output_embeddings().weight.data_ptr())

        targets = [name for name, _ in model.named_modules() if is_text_decoder_target(name)]
        model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.10, bias="none", task_type="CAUSAL_LM", target_modules=r"^model\.layers\.\d+\.self_attn\.(q_proj|k_proj|v_proj|o_proj)$"))
        attached = lora_leaf_modules(model)
        if len(targets) != 184 or len(attached) != 184:
            raise RuntimeError(f"LoRA target mismatch: {len(targets)}/{len(attached)}")
        model.train()
        trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
        if sum(parameter.numel() for parameter in trainable) != 10_665_984:
            raise RuntimeError("trainable parameter invariant failed")
        stage("lora", inventory=parameter_inventory(model), tied=model.get_input_embeddings().weight.data_ptr() == tied_pointer == model.get_output_embeddings().weight.data_ptr(), target_count=len(attached))
        optimizer = torch.optim.AdamW(trainable, lr=5e-5)

        torch.cuda.reset_peak_memory_stats()
        optimizer.zero_grad(set_to_none=True)
        batch = make_batch(tokenizer, longest, 512, torch.device("cuda:0"))
        started = time.perf_counter()
        output = model(**batch)
        logits_finite = bool(torch.isfinite(output.logits).all())
        loss = output.loss
        if not logits_finite or not torch.isfinite(loss):
            raise RuntimeError("non-finite logits or loss")
        loss.backward()
        gradients = grad_report(model)
        if not gradients["all_finite"] or gradients["frozen_gradient_names"]:
            raise RuntimeError(f"gradient validation failed: {gradients}")
        optimizer.step()
        torch.cuda.synchronize()
        result["longest"] = {"loss": float(loss.detach().cpu()), "seconds": time.perf_counter() - started, "logits_finite": logits_finite, "gradients": gradients, **cuda_metrics(), "nvidia": NvidiaMonitor.sample()}
        output = loss = batch = None

        smoke_losses: list[float] = []
        smoke_times: list[float] = []
        torch.cuda.reset_peak_memory_stats()
        for first, second in ((smoke[0], smoke[1]), (smoke[2], smoke[3])):
            optimizer.zero_grad(set_to_none=True)
            started = time.perf_counter()
            pair: list[torch.Tensor] = []
            for row in (first, second):
                output = model(**make_batch(tokenizer, row, 512, torch.device("cuda:0")))
                if not torch.isfinite(output.loss):
                    raise RuntimeError(f"non-finite smoke loss: {row['id']}")
                (output.loss / 2).backward()
                pair.append(output.loss.detach())
            gradients = grad_report(model)
            if not gradients["all_finite"] or gradients["frozen_gradient_names"]:
                raise RuntimeError(f"smoke gradient validation failed: {gradients}")
            optimizer.step()
            torch.cuda.synchronize()
            smoke_losses.append(float(torch.stack(pair).mean().cpu()))
            smoke_times.append(time.perf_counter() - started)
        result["smoke"] = {"losses": smoke_losses, "step_seconds": smoke_times, "total_seconds": sum(smoke_times), **cuda_metrics(), "nvidia": NvidiaMonitor.sample()}

        if args.mode == "precision":
            model.save_pretrained(adapter_dir, safe_serialization=True)
            result["adapter_save"] = {"path": str(adapter_dir), "files": sorted(path.name for path in adapter_dir.iterdir() if path.is_file())}
            optimizer = model = trainable = input_weight = output_weight = output = loss = batch = None
            pair = gradients = None
            gc.collect(); torch.cuda.empty_cache(); torch.cuda.ipc_collect()
            base, reload_info = load_base(args.model_path, quantization)
            reloaded = PeftModel.from_pretrained(base, adapter_dir, local_files_only=True, is_trainable=False)
            reload_targets = lora_leaf_modules(reloaded)
            config_entry = next(iter(reloaded.peft_config.values()))
            adapter_dtypes = sorted({str(parameter.dtype) for name, parameter in reloaded.named_parameters() if "lora_" in name})
            if len(reload_targets) != 184 or not reloaded.peft_config:
                raise RuntimeError("adapter reload target/activation failure")
            result["adapter_reload"] = {"active": True, "target_count": len(reload_targets), "base_model_name_or_path": config_entry.base_model_name_or_path, "adapter_dtypes": adapter_dtypes, "missing_keys": sorted(reload_info["missing_keys"]), "tied": base.get_input_embeddings().weight.data_ptr() == base.get_output_embeddings().weight.data_ptr()}
        result["status"] = "PASS"
    except Exception as exc:
        result["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        model = optimizer = tokenizer = batch = output = loss = base = reloaded = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache(); torch.cuda.ipc_collect()
        monitor.stop()
        result.update(monitor.maxima())
        result["cleanup"] = {**cuda_metrics(), "nvidia": NvidiaMonitor.sample()}
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
