from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.gpu_resource_gate import GpuResourceGate


class VoiceUnavailable(RuntimeError):
    pass


class VoiceServiceClient:
    """HTTP adapter for the separately isolated Style-Bert-VITS2 service."""

    def __init__(self, root: Path, repository_root: Path, conversations, base_url: str = "http://127.0.0.1:8766",
                 gpu_gate: GpuResourceGate | None = None) -> None:
        self.root, self.repository_root = root.resolve(), repository_root.resolve()
        self.artifact_root = (self.root / "artifacts" / "voice").resolve()
        self.conversations, self.base_url = conversations, base_url.rstrip("/")
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._state, self._error = "AVAILABLE", None
        self.gpu_gate = gpu_gate

    def _request(self, path: str, payload: dict | None = None, timeout: int = 10) -> dict:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.base_url + path, data=data,
            headers={"Content-Type": "application/json"} if data else {}, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try: detail = json.loads(error.read().decode("utf-8")).get("error", str(error))
            except Exception: detail = str(error)
            raise VoiceUnavailable(detail) from error
        except (OSError, urllib.error.URLError) as error:
            raise VoiceUnavailable(str(error)) from error

    def _start(self) -> None:
        try:
            self._request("/api/meta", timeout=2); return
        except VoiceUnavailable:
            pass
        executable = self.root / "runtime" / "voice-venv" / "py310-cu128" / "Scripts" / "python.exe"
        if not executable.is_file(): raise VoiceUnavailable(f"Voice runtime missing: {executable}")
        env = os.environ.copy(); env.update({"SHION_DATA_ROOT": str(self.root), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
        self._process = subprocess.Popen([str(executable), "-u", "voice/server.py", "--port", "8766"],
            cwd=self.repository_root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self._process.poll() is not None: raise VoiceUnavailable("Voice service failed during startup")
            try: self._request("/api/meta", timeout=2); return
            except VoiceUnavailable: time.sleep(.25)
        raise VoiceUnavailable("Voice service startup timed out")

    def metadata(self, ensure_running: bool = False) -> dict:
        if ensure_running:
            self._start()
        try:
            data = self._request("/api/meta", timeout=2)
            approved = [item for item in data.get("presets", []) if item.get("owner_approved") is True]
            if self._state not in {"READY", "LOADING", "GENERATING", "ERROR"}: self._state = "AVAILABLE"
            return {"state": self._state, "approved_presets": approved, "developer_models": data.get("models", {}), "error": None}
        except VoiceUnavailable as error:
            if self._state not in {"READY", "LOADING", "GENERATING", "ERROR"}: self._state = "AVAILABLE"
            return {"state": self._state, "approved_presets": [], "developer_models": {}, "error": None}

    def generate(self, message_id: str, response_version: int, preset_id: str | None,
                 developer_model: str | None = None, developer_style: str | None = None,
                 retry: bool = False, session_id: str | None = None) -> dict:
        if self.gpu_gate:
            selection = preset_id or f"developer:{developer_model}:{developer_style or ''}"
            key = ("message", message_id, response_version, selection)
            identity = {"session_id": session_id, "message_id": message_id, "response_version": response_version}
            return self.gpu_gate.submit_voice(key, identity, lambda: self._generate(
                message_id, response_version, preset_id, developer_model, developer_style, retry))
        return self._generate(message_id, response_version, preset_id, developer_model, developer_style, retry)

    def _generate(self, message_id: str, response_version: int, preset_id: str | None,
                  developer_model: str | None = None, developer_style: str | None = None,
                  retry: bool = False) -> dict:
        if not self.conversations: raise VoiceUnavailable("Persistent history is required for Read Aloud")
        source = self.conversations.get_assistant_version(message_id, response_version)
        with self._lock:
            self._state, self._error = "LOADING", None
            try:
                self._start(); meta = self._request("/api/meta", timeout=5)
                approved = {item["preset_name"]: item for item in meta.get("presets", []) if item.get("owner_approved") is True}
                if not preset_id and not developer_model and "SHION Default" in approved:
                    preset_id = "SHION Default"
                if preset_id:
                    if preset_id not in approved: raise ValueError("Voice preset is not Owner-approved")
                    settings = dict(approved[preset_id])
                elif developer_model:
                    model = meta.get("models", {}).get(developer_model)
                    if not model: raise ValueError("Developer voice model is unavailable")
                    styles = model.get("styles") or []
                    if not styles: raise ValueError("Developer voice model has no available styles")
                    style = developer_style or styles[0]
                    if style not in styles: raise ValueError("Developer voice style is unavailable")
                    settings = {"voice_model": developer_model, "style": style, "style_weight": 1.0,
                        "length": 1.0, "pitch_scale": 1.0, "intonation_scale": 1.0, "sdp_ratio": .2,
                        "noise": .6, "noise_w": .8, "assist_text": "", "assist_text_weight": .7}
                    preset_id = f"developer:{developer_model}:{style}"
                else: raise ValueError("No approved SHION voice preset")
                display_text = self.normalize(source["text"])
                settings["text"] = self.conversations.apply_pronunciation(display_text, source["character_id"])
                self._state = "GENERATING"
                generated = self._request("/api/generate", settings, timeout=180)
                target = Path(generated["path"]).resolve()
                if self.artifact_root != target and self.artifact_root not in target.parents:
                    raise VoiceUnavailable("Voice service returned an unsafe artifact path")
                artifact_id = str(uuid.uuid4()); created = datetime.now(timezone.utc).isoformat(timespec="seconds")
                target = self._claim_artifact(target, artifact_id)
                attempt = self.conversations.next_voice_attempt(message_id, response_version, preset_id)
                generation_metadata = {**generated["metrics"], "voice_model_id": generated["settings"]["voice_model"],
                    "voice_style": generated["settings"]["style"], "voice_preset_id": preset_id}
                record = {"artifact_id": artifact_id, "message_id": message_id, "response_version": response_version,
                    "session_id": source["session_id"], "source_type": "message", "source_text": display_text,
                    "tts_text": settings["text"], "character_id": source["character_id"],
                    "voice_model_id": generated["settings"]["voice_model"], "voice_preset_id": preset_id,
                    "voice_style": generated["settings"]["style"],
                    "voice_revision": self._voice_revision(meta, generated["settings"]["voice_model"]),
                    "created_at": created, "duration": generated["metrics"]["wav_duration_seconds"],
                    "latency_seconds": generated["metrics"].get("latency_seconds", 0), "file_size_bytes": target.stat().st_size,
                    "parameters": self._voice_parameters(generated["settings"]),
                    "relative_path": str(target.relative_to(self.artifact_root)), "attempt": attempt,
                    "generation_metadata": generation_metadata}
                self.conversations.save_voice_artifact(record)
                self._state = "READY"
                return {**self._public_artifact(record), "generation_metadata": generation_metadata,
                    "audio_url": f"/api/voice/artifacts/{artifact_id}", "retry": retry}
            except Exception as error:
                self._state, self._error = "ERROR", str(error)
                raise

    @staticmethod
    def normalize(text: str) -> str:
        import re
        value = re.sub(r"```[\s\S]*?```", " コード省略 ", text)
        value = re.sub(r"https?://\S+", " URL ", value)
        value = re.sub(r"[*_#>`]+", "", value)
        return re.sub(r"\s+", " ", value).strip()[:500]

    @staticmethod
    def _voice_revision(meta: dict, model_id: str) -> str | None:
        for item in meta.get("managed_models", []):
            if item.get("id") == model_id: return item.get("revision")
        return None

    @staticmethod
    def _voice_parameters(settings: dict) -> dict:
        allowed = {"style_weight", "length", "pitch_scale", "intonation_scale", "sdp_ratio", "noise", "noise_w",
                   "assist_text_weight"}
        return {key: settings[key] for key in allowed if key in settings and isinstance(settings[key], (int, float))}

    def _claim_artifact(self, source: Path, artifact_id: str) -> Path:
        destination = (self.artifact_root / "indexed" / f"{artifact_id}.wav").resolve()
        if self.artifact_root not in destination.parents: raise VoiceUnavailable("unsafe Voice artifact destination")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source != destination:
            source.replace(destination)
        return destination

    @staticmethod
    def _public_artifact(record: dict) -> dict:
        return {key: value for key, value in record.items() if key not in {"relative_path", "generation_metadata"}}

    def artifact(self, artifact_id: str) -> tuple[Path, dict]:
        record = self.conversations.get_voice_artifact(artifact_id)
        target = (self.artifact_root / record["relative_path"]).resolve()
        if self.artifact_root not in target.parents or not target.is_file() or target.suffix.lower() != ".wav":
            raise FileNotFoundError(artifact_id)
        return target, record

    def generate_lab(self, text: str, parameters: dict, request_id: str | None = None,
                     character_id: str = "shion") -> dict:
        """Generate a persistent Voice Lab artifact without changing SHION Default."""
        if self.gpu_gate:
            identity = {"session_id": request_id, "request_id": request_id}
            return self.gpu_gate.submit_voice(("lab", request_id), identity,
                lambda: self._generate_lab(text, parameters, character_id))
        return self._generate_lab(text, parameters, character_id)

    def _generate_lab(self, text: str, parameters: dict, character_id: str = "shion") -> dict:
        normalized = self.normalize(text)
        if not normalized:
            raise ValueError("TTS text is required")
        allowed = {"style_weight": (0.0, 2.0), "length": (0.7, 1.5), "pitch_scale": (0.8, 1.2), "intonation_scale": (0.5, 1.5)}
        settings = {}
        for name, (minimum, maximum) in allowed.items():
            value = float(parameters.get(name, 1.0))
            if not minimum <= value <= maximum:
                raise ValueError(f"{name} is outside the allowlist")
            settings[name] = value
        with self._lock:
            self._start(); meta = self._request("/api/meta", timeout=5)
            approved = {item["preset_name"]: item for item in meta.get("presets", []) if item.get("owner_approved") is True}
            preset = approved.get("SHION Default")
            if not preset: raise VoiceUnavailable("SHION Default is unavailable")
            transformed = self.conversations.apply_pronunciation(normalized, character_id)
            payload = {**preset, **settings, "text": transformed}
            self._state = "GENERATING"
            generated = self._request("/api/generate", payload, timeout=180)
            target = Path(generated["path"]).resolve()
            if self.artifact_root not in target.parents: raise VoiceUnavailable("unsafe Voice artifact")
            artifact_id = str(uuid.uuid4())
            target = self._claim_artifact(target, artifact_id)
            record = {"artifact_id": artifact_id, "message_id": None, "response_version": None, "session_id": None,
                      "source_type": "lab", "source_text": normalized, "tts_text": transformed, "character_id": character_id,
                      "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "voice_model_id": generated["settings"]["voice_model"], "voice_style": generated["settings"]["style"],
                      "voice_revision": self._voice_revision(meta, generated["settings"]["voice_model"]),
                      "voice_preset_id": "SHION Default", "duration": generated["metrics"]["wav_duration_seconds"],
                      "latency_seconds": generated["metrics"]["latency_seconds"], "parameters": settings,
                      "text_preview": normalized[:80], "file_size_bytes": target.stat().st_size,
                      "relative_path": str(target.relative_to(self.artifact_root)), "attempt": 1,
                      "generation_metadata": generated["metrics"]}
            self.conversations.save_voice_artifact(record)
            self._state = "READY"
            return {**self._public_artifact(record), "generation_metadata": generated["metrics"],
                "audio_url": f"/api/voice/artifacts/{artifact_id}"}

    def list_artifacts(self, character_id: str = "shion") -> list[dict]:
        records = self.conversations.list_voice_artifact_index(character_id)
        for record in records:
            target = (self.artifact_root / record["relative_path"]).resolve()
            available = self.artifact_root in target.parents and target.is_file() and target.suffix.lower() == ".wav"
            record["available"] = available
            record["audio_url"] = f"/api/voice/artifacts/{record['artifact_id']}" if available else None
            if available and not record["file_size_bytes"]:
                record["file_size_bytes"] = target.stat().st_size
            record["text_preview"] = record["source_text"][:80] or "Existing message artifact"
        return [self._public_artifact(record) for record in records]

    def set_favorite(self, artifact_id: str, favorite: bool) -> dict:
        self.conversations.set_voice_artifact_favorite(artifact_id, favorite)
        return self._public_artifact(self.conversations.get_voice_artifact(artifact_id))

    def delete_artifact(self, artifact_id: str) -> dict:
        record = self.conversations.get_voice_artifact(artifact_id)
        target = (self.artifact_root / record["relative_path"]).resolve()
        if self.artifact_root not in target.parents or target.suffix.lower() != ".wav":
            raise VoiceUnavailable("unsafe Voice artifact")
        if target.is_file():
            target.unlink()
        deleted = self.conversations.delete_voice_artifact(artifact_id)
        return {"artifact_id": artifact_id, "deleted": True, "file_removed": not target.exists(), "source_type": deleted["source_type"]}

    def retry_artifact(self, artifact_id: str, request_id: str) -> dict:
        record = self.conversations.get_voice_artifact(artifact_id)
        if record["source_type"] == "message" and record.get("message_id"):
            preset = record["voice_preset_id"]
            if preset.startswith("developer:"):
                _, model_id, style = preset.split(":", 2)
                return self.generate(record["message_id"], int(record["response_version"]), None, model_id, style,
                                     retry=True, session_id=request_id)
            return self.generate(record["message_id"], int(record["response_version"]), preset, retry=True, session_id=request_id)
        return self.generate_lab(record["source_text"], record["parameters"], request_id, record["character_id"])

    def status(self) -> dict:
        meta = self.metadata(False)
        gate = self.gpu_gate.status() if self.gpu_gate else None
        state = gate["state"] if gate and gate["state"] in {"WAITING_FOR_GPU", "GENERATING"} else self._state
        return {**meta, "state": state, "error": self._error, "resource_gate": gate}

    def close(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try: self._process.wait(10)
            except subprocess.TimeoutExpired: self._process.kill()
