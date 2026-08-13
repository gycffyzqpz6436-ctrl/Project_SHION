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


class VoiceUnavailable(RuntimeError):
    pass


class VoiceServiceClient:
    """HTTP adapter for the separately isolated Style-Bert-VITS2 service."""

    def __init__(self, root: Path, repository_root: Path, conversations, base_url: str = "http://127.0.0.1:8766") -> None:
        self.root, self.repository_root = root.resolve(), repository_root.resolve()
        self.artifact_root = (self.root / "artifacts" / "voice").resolve()
        self.conversations, self.base_url = conversations, base_url.rstrip("/")
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._state, self._error = "AVAILABLE", None

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
                settings["text"] = self.normalize(source["text"])
                self._state = "GENERATING"
                generated = self._request("/api/generate", settings, timeout=180)
                target = Path(generated["path"]).resolve()
                if self.artifact_root != target and self.artifact_root not in target.parents:
                    raise VoiceUnavailable("Voice service returned an unsafe artifact path")
                artifact_id = str(uuid.uuid4()); created = datetime.now(timezone.utc).isoformat(timespec="seconds")
                attempt = self.conversations.next_voice_attempt(message_id, response_version, preset_id)
                generation_metadata = {**generated["metrics"], "voice_model_id": generated["settings"]["voice_model"],
                    "voice_style": generated["settings"]["style"], "voice_preset_id": preset_id}
                record = {"artifact_id": artifact_id, "message_id": message_id, "response_version": response_version,
                    "voice_model_id": generated["settings"]["voice_model"], "voice_preset_id": preset_id,
                    "voice_style": generated["settings"]["style"],
                    "voice_revision": self._voice_revision(meta, generated["settings"]["voice_model"]),
                    "created_at": created, "duration": generated["metrics"]["wav_duration_seconds"],
                    "relative_path": str(target.relative_to(self.artifact_root)), "attempt": attempt,
                    "generation_metadata": generation_metadata}
                self.conversations.save_voice_artifact(record)
                self._state = "READY"
                return {**record, "audio_url": f"/api/voice/artifacts/{artifact_id}", "retry": retry}
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

    def artifact(self, artifact_id: str) -> tuple[Path, dict]:
        record = self.conversations.get_voice_artifact(artifact_id)
        target = (self.artifact_root / record["relative_path"]).resolve()
        if self.artifact_root not in target.parents or not target.is_file() or target.suffix.lower() != ".wav":
            raise FileNotFoundError(artifact_id)
        return target, record

    def status(self) -> dict:
        meta = self.metadata(False)
        return {**meta, "state": self._state, "error": self._error}

    def close(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try: self._process.wait(10)
            except subprocess.TimeoutExpired: self._process.kill()
