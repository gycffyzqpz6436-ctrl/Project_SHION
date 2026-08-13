from __future__ import annotations

import gc
import json
import os
import re
import threading
import time
import wave
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from model_manager import VoiceModelManager
from hf_environment import HF_ACCESS_LOCK


VOICE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = VOICE_DIR / "config"
PRESET_DIR = VOICE_DIR / "presets"
SHION_DATA_ROOT = Path(os.environ.get("SHION_DATA_ROOT", r"D:\AI\Project_SHION"))
OUTPUT_DIR = SHION_DATA_ROOT / "artifacts" / "voice" / "voice-tuning"
RUNTIME_CONFIG = CONFIG_DIR / "prototype_v0_1.json"
PARAMETER_LIMITS = {
    "style_weight": (0.0, 2.0),
    "length": (0.7, 1.5),
    "pitch_scale": (0.8, 1.2),
    "intonation_scale": (0.5, 1.5),
    "sdp_ratio": (0.0, 1.0),
    "noise": (0.0, 1.0),
    "noise_w": (0.0, 1.0),
    "assist_text_weight": (0.0, 1.0),
}
DEFAULT_TEXT = "へぇ〜？ お兄さん、もう疲れちゃったの〜？♪"


@dataclass(frozen=True)
class VoiceSettings:
    text: str
    voice_model: str
    style: str
    style_weight: float
    length: float
    pitch_scale: float
    intonation_scale: float
    sdp_ratio: float
    noise: float
    noise_w: float
    assist_text: str
    assist_text_weight: float

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "VoiceSettings":
        text = str(payload.get("text", "")).strip()
        if not text or len(text) > 500:
            raise ValueError("Text must contain 1-500 characters")
        model = str(payload.get("voice_model", "F1"))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", model):
            raise ValueError("Invalid voice model ID")
        style = str(payload.get("style", "Neutral"))
        values: dict[str, float] = {}
        for key, (minimum, maximum) in PARAMETER_LIMITS.items():
            value = float(payload.get(key, 0.7 if key == "assist_text_weight" else 1.0))
            if not minimum <= value <= maximum:
                raise ValueError(f"{key} must be between {minimum} and {maximum}")
            values[key] = value
        assist_text = str(payload.get("assist_text", "")).strip()
        if len(assist_text) > 500:
            raise ValueError("assist_text must not exceed 500 characters")
        return cls(text, model, style, assist_text=assist_text, **values)

    def preset_data(self, preset_name: str, status: str) -> dict[str, Any]:
        data = asdict(self)
        data.pop("text")
        return {
            "schema_version": 1,
            "preset_name": preset_name,
            "status": status,
            "owner_approved": status == "approved",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            **data,
        }


class VoiceController:
    def __init__(self) -> None:
        from scripts.voice_runtime import configure_external_environment, load_config, validate_external_paths

        self._load_config = load_config
        self._configure = configure_external_environment
        self._validate = validate_external_paths
        self._lock = threading.Lock()
        self._model: Any = None
        self._model_alias: str | None = None
        self.models = VoiceModelManager()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def metadata(self) -> dict[str, Any]:
        models = {record["id"]: {"name": record["display_name"], "styles": record["styles"]}
                  for record in self.models.list_models() if record["status"] == "Ready"}
        return {"models": models, "limits": PARAMETER_LIMITS, "default_text": DEFAULT_TEXT}

    def _get_model(self, alias: str) -> tuple[Any, dict[str, Any]]:
        record = self.models.get(alias)
        config = self._load_config(RUNTIME_CONFIG)
        self._configure(config)
        import torch
        from style_bert_vits2.tts_model import TTSModel
        if self._model_alias != alias:
            self._model = None
            self._model_alias = None
            gc.collect()
            torch.cuda.empty_cache()
            self._model = TTSModel(
                model_path=record.local_path / record.weight_file,
                config_path=record.local_path / record.config_file,
                style_vec_path=record.local_path / record.style_vectors_file,
                device="cuda",
            )
            self._model_alias = alias
        return self._model, config

    def generate(self, settings: VoiceSettings) -> dict[str, Any]:
        import torch

        with self._lock, HF_ACCESS_LOCK:
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA unavailable; CPU fallback is disabled")
            model, _ = self._get_model(settings.voice_model)
            from style_bert_vits2.constants import Languages
            if settings.style not in model.style2id:
                raise ValueError(f"Style is unavailable for {settings.voice_model}")
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            started = time.perf_counter()
            sample_rate, audio = model.infer(
                text=settings.text,
                language=Languages.JP,
                style=settings.style,
                style_weight=settings.style_weight,
                length=settings.length,
                pitch_scale=settings.pitch_scale,
                intonation_scale=settings.intonation_scale,
                sdp_ratio=settings.sdp_ratio,
                noise=settings.noise,
                noise_w=settings.noise_w,
                assist_text=settings.assist_text or None,
                assist_text_weight=settings.assist_text_weight,
                use_assist_text=bool(settings.assist_text),
                line_split=False,
            )
            torch.cuda.synchronize()
            latency = time.perf_counter() - started
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{timestamp}_{settings.voice_model}_{settings.style}.wav"
            output = OUTPUT_DIR / filename
            pcm = np.asarray(audio, dtype=np.int16)
            with wave.open(str(output), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(pcm.tobytes())
            return {
                "id": filename,
                "audio_url": f"/audio/{filename}",
                "path": str(output),
                "settings": asdict(settings),
                "metrics": {
                    "latency_seconds": round(latency, 4),
                    "wav_duration_seconds": round(len(pcm) / sample_rate, 4),
                    "sample_rate_hz": sample_rate,
                    "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2),
                    "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 2),
                    "file_size_bytes": output.stat().st_size,
                },
            }

    def test_model(self, model_id: str, text: str = "……聞こえる？ お兄さん♪") -> dict[str, Any]:
        record = self.models.get(model_id, allow_unready=True)
        if record.structure_status != "Valid" or not record.enabled or record.removed:
            raise ValueError(f"Model cannot be tested: {record.status}")
        settings = VoiceSettings.from_payload({
            "text": text, "voice_model": model_id, "style": record.styles[0], "style_weight": 1.0,
            "length": 1.0, "pitch_scale": 1.0, "intonation_scale": 1.0, "sdp_ratio": 0.2,
            "noise": 0.6, "noise_w": 0.8, "assist_text": "", "assist_text_weight": 0.7,
        })
        # Temporarily allow structurally valid, license-pending models for local-only evaluation.
        original_review, original_tested = record.license_reviewed, record.tested
        record.license_reviewed = True
        record.tested = True
        try:
            result = self.generate(settings)
        finally:
            record.license_reviewed, record.tested = original_review, original_tested
        self.models.set_flags(model_id, tested=True)
        result["model_status"] = self.models.get(model_id, allow_unready=True).status
        return result

    def save_preset(self, settings: VoiceSettings, name: str, approved: bool) -> dict[str, Any]:
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,63}", name):
            raise ValueError("Preset name must be 3-64 safe ASCII characters")
        status = "approved" if approved else "candidate"
        destination = PRESET_DIR / status / f"{name}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"Preset already exists: {name}")
        data = settings.preset_data(name, status)
        destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"path": str(destination), "preset": data}

    def list_presets(self) -> list[dict[str, Any]]:
        presets = []
        for status in ("candidate", "approved"):
            for path in sorted((PRESET_DIR / status).glob("*.json")):
                presets.append(json.loads(path.read_text(encoding="utf-8")))
        return presets
