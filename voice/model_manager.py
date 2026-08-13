from __future__ import annotations

import gc
import json
import os
import re
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hf_environment import explicit_huggingface_online, offline_status


SHION_DATA_ROOT = Path(os.environ.get("SHION_DATA_ROOT", r"D:\AI\Project_SHION"))
VOICE_ROOT = SHION_DATA_ROOT
MODELS_ROOT = SHION_DATA_ROOT / "models" / "voice"
REGISTRY_PATH = SHION_DATA_ROOT / "data" / "voice" / "models.json"
TEMP_ROOT = SHION_DATA_ROOT / "temp" / "voice"
HF_CACHE = SHION_DATA_ROOT / "cache" / "huggingface" / "hub"
WEIGHT_SUFFIXES = {".safetensors", ".pth", ".pt"}


class SavedRevisionUnavailable(ValueError):
    def __init__(self, repo_id: str, revision: str) -> None:
        super().__init__("Saved revision is no longer available.")
        self.repo_id = repo_id
        self.revision = revision
KNOWN_MODELS = {
    "jvnv/jvnv-F1-jp": {
        "id": "F1", "display_name": "JVNV F1", "speaker": "F1",
        "source": "huggingface", "repository": "litagin/style_bert_vits2_jvnv",
        "revision": "205830ca1d49e666ddfbf2a755f0108e9cade4dd", "license": "CC-BY-SA-4.0",
        "author": "litagin", "commercial_use": "Allowed under license", "redistribution": "Allowed under ShareAlike terms",
        "credit_requirement": "Attribution required", "additional_terms": "Share adaptations under the same license",
        "license_reviewed": True, "tested": True,
    },
    "jvnv/jvnv-F2-jp": {
        "id": "F2", "display_name": "JVNV F2", "speaker": "F2",
        "source": "huggingface", "repository": "litagin/style_bert_vits2_jvnv",
        "revision": "205830ca1d49e666ddfbf2a755f0108e9cade4dd", "license": "CC-BY-SA-4.0",
        "author": "litagin", "commercial_use": "Allowed under license", "redistribution": "Allowed under ShareAlike terms",
        "credit_requirement": "Attribution required", "additional_terms": "Share adaptations under the same license",
        "license_reviewed": True, "tested": True,
    },
}


@dataclass
class ModelRecord:
    id: str
    display_name: str
    relative_path: str
    speaker: str = "Unknown"
    styles: list[str] = field(default_factory=list)
    size_bytes: int = 0
    source: str = "local"
    repository: str = ""
    revision: str = ""
    license: str = "Unknown"
    author: str = "Unknown"
    commercial_use: str = "Unknown"
    redistribution: str = "Unknown"
    credit_requirement: str = "Unknown"
    additional_terms: str = "Manual review required"
    enabled: bool = True
    removed: bool = False
    license_reviewed: bool = False
    tested: bool = False
    structure_status: str = "Invalid"
    reasons: list[str] = field(default_factory=list)
    config_file: str = ""
    weight_file: str = ""
    style_vectors_file: str = ""

    @property
    def local_path(self) -> Path:
        return (MODELS_ROOT / self.relative_path).resolve()

    @property
    def status(self) -> str:
        if self.structure_status != "Valid":
            return self.structure_status
        if not self.license_reviewed:
            return "License Review Required"
        return "Ready" if self.tested and self.enabled and not self.removed else "Disabled"

    def public(self) -> dict[str, Any]:
        return {**asdict(self), "local_path": str(self.local_path), "status": self.status}


class VoiceModelManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, ModelRecord] = {}
        MODELS_ROOT.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        HF_CACHE.mkdir(parents=True, exist_ok=True)
        self.refresh()

    @staticmethod
    def _safe_id(value: str) -> str:
        result = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
        return result[:64] or "voice_model"

    def _load_state(self) -> dict[str, Any]:
        if not REGISTRY_PATH.exists():
            return {"schema_version": 1, "models": {}}
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def _save_state(self) -> None:
        data = {"schema_version": 1, "models": {r.relative_path: {
            key: getattr(r, key) for key in (
                "id", "display_name", "speaker", "source", "repository", "revision", "license", "author",
                "commercial_use", "redistribution", "credit_requirement", "additional_terms", "enabled", "removed",
                "license_reviewed", "tested"
            )
        } for r in self._records.values()}}
        temporary = REGISTRY_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(REGISTRY_PATH)

    def _inspect_folder(self, folder: Path, metadata: dict[str, Any]) -> ModelRecord:
        relative = folder.resolve().relative_to(MODELS_ROOT.resolve()).as_posix()
        config_files = list(folder.glob("config.json"))
        vectors = list(folder.glob("style_vectors.npy"))
        weights = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in WEIGHT_SUFFIXES]
        record = ModelRecord(
            id=metadata.get("id", self._safe_id(relative)), display_name=metadata.get("display_name", folder.name),
            relative_path=relative, **{k: v for k, v in metadata.items() if k in ModelRecord.__dataclass_fields__ and k not in {"id", "display_name", "relative_path"}}
        )
        if not config_files: record.reasons.append("config.json is missing")
        if not vectors: record.reasons.append("style_vectors.npy is missing")
        if not weights: record.reasons.append("model weight is missing")
        if len(weights) > 1: record.reasons.append("multiple model weights found; selection is ambiguous")
        record.structure_status = "Incomplete" if record.reasons else "Valid"
        if record.reasons:
            return record
        try:
            config = json.loads(config_files[0].read_text(encoding="utf-8"))
            data = config["data"]
            record.styles = list(data["style2id"])
            record.speaker = metadata.get("speaker") or next(iter(data.get("spk2id", {"Unknown": 0})))
            record.config_file, record.weight_file, record.style_vectors_file = config_files[0].name, weights[0].name, vectors[0].name
            record.size_bytes = sum(p.stat().st_size for p in (config_files[0], weights[0], vectors[0]))
            if not record.styles:
                raise ValueError("style2id is empty")
        except Exception as exc:
            record.structure_status = "Invalid"
            record.reasons.append(f"Invalid config: {exc}")
        return record

    def refresh(self) -> list[dict[str, Any]]:
        with self._lock:
            state = self._load_state().get("models", {})
            records: dict[str, ModelRecord] = {}
            folders = {p.parent for p in MODELS_ROOT.rglob("config.json")}
            folders.update(p.parent for p in MODELS_ROOT.rglob("style_vectors.npy"))
            folders.update(p.parent for p in MODELS_ROOT.rglob("*.safetensors"))
            folders.update(p.parent for p in MODELS_ROOT.rglob("*.pth"))
            folders.update(p.parent for p in MODELS_ROOT.rglob("*.pt"))
            for folder in sorted(folders):
                relative = folder.resolve().relative_to(MODELS_ROOT.resolve()).as_posix()
                metadata = {**KNOWN_MODELS.get(relative, {}), **state.get(relative, {})}
                if relative in KNOWN_MODELS:
                    for key in ("source", "repository", "revision", "license", "author", "commercial_use", "redistribution", "credit_requirement", "additional_terms"):
                        metadata[key] = KNOWN_MODELS[relative][key]
                record = self._inspect_folder(folder, metadata)
                records[record.id] = record
            self._records = records
            self._save_state()
            return self.list_models()

    def list_models(self) -> list[dict[str, Any]]:
        return [record.public() for record in sorted(self._records.values(), key=lambda x: x.display_name.lower())]

    def get(self, model_id: str, allow_unready: bool = False) -> ModelRecord:
        record = self._records.get(model_id)
        if not record or record.removed:
            raise KeyError("Unknown or removed model")
        if not allow_unready and record.status != "Ready":
            raise ValueError(f"Model is not Ready: {record.status}")
        return record

    def set_flags(self, model_id: str, *, enabled: bool | None = None, removed: bool | None = None, license_reviewed: bool | None = None, tested: bool | None = None) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(model_id)
            if not record:
                raise KeyError("Unknown model")
            for key, value in (("enabled", enabled), ("removed", removed), ("license_reviewed", license_reviewed), ("tested", tested)):
                if value is not None: setattr(record, key, value)
            self._save_state()
            return record.public()

    def register_local(self, path: str, display_name: str = "") -> dict[str, Any]:
        folder = Path(path).resolve()
        try:
            folder.relative_to(MODELS_ROOT.resolve())
        except ValueError as exc:
            raise ValueError(f"Local registration is restricted to {MODELS_ROOT}") from exc
        if not folder.is_dir():
            raise ValueError("Folder does not exist")
        self.refresh()
        match = next((r for r in self._records.values() if r.local_path == folder), None)
        if not match:
            raise ValueError("No Style-Bert-VITS2 model structure detected")
        if display_name:
            match.display_name = display_name[:80]
            self._save_state()
        return match.public()

    def preview_huggingface(self, repo_id: str, revision: str = "") -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo_id):
            raise ValueError("Invalid Hugging Face repo ID")
        with explicit_huggingface_online():
            from huggingface_hub import HfApi
            from huggingface_hub.errors import RevisionNotFoundError
            api = HfApi()
            try:
                info = api.model_info(repo_id, revision=revision or None, files_metadata=True)
            except RevisionNotFoundError as exc:
                raise SavedRevisionUnavailable(repo_id, revision) from exc
            refs = api.list_repo_refs(repo_id, repo_type="model")
        files = [{"path": item.rfilename, "size": item.size or 0} for item in info.siblings]
        candidates: dict[str, set[str]] = {}
        for item in files:
            parent = str(Path(item["path"]).parent).replace("\\", "/")
            candidates.setdefault(parent, set()).add(Path(item["path"]).name)
        detected = [folder for folder, names in candidates.items() if "config.json" in names and "style_vectors.npy" in names and any(Path(n).suffix.lower() in WEIGHT_SUFFIXES for n in names)]
        card = info.card_data or {}
        license_value = card.get("license") or "Unknown"
        matching_branches = [branch.name for branch in refs.branches if branch.target_commit == info.sha]
        default_branch = "main" if "main" in matching_branches else (matching_branches[0] if matching_branches else "Unknown")
        candidate_sizes = {folder: sum(item["size"] for item in files if item["path"].startswith(folder + "/") or (folder == "." and "/" not in item["path"])) for folder in detected}
        return {"repo_id": repo_id, "default_branch": default_branch, "revision": info.sha, "author": repo_id.split("/", 1)[0], "license": license_value,
                "license_review_required": license_value == "Unknown", "download_size": sum(x["size"] for x in files if any(x["path"] == d or x["path"].startswith(d + "/") for d in detected)),
                "candidates": detected, "candidate_sizes": candidate_sizes, "files": files}

    def refresh_huggingface_revision(self, repo_id: str) -> dict[str, Any]:
        return self.preview_huggingface(repo_id, revision="")

    def download_huggingface(self, repo_id: str, revision: str, candidate: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise SavedRevisionUnavailable(repo_id, revision)
        preview = self.preview_huggingface(repo_id, revision)
        if preview["revision"] != revision:
            raise SavedRevisionUnavailable(repo_id, revision)
        if candidate not in preview["candidates"]:
            raise ValueError("Candidate was not found in preview")
        destination = MODELS_ROOT / "huggingface" / self._safe_id(repo_id) / preview["revision"][:12] / self._safe_id(candidate)
        if destination.exists():
            return {"reused": True, "path": str(destination)}
        temporary = TEMP_ROOT / f"voice-model-{self._safe_id(repo_id)}-{preview['revision'][:12]}"
        if temporary.exists():
            shutil.rmtree(temporary)
        patterns = [f"{candidate}/*"] if candidate != "." else ["config.json", "style_vectors.npy", "*.safetensors", "*.pth", "*.pt"]
        with explicit_huggingface_online():
            from huggingface_hub import snapshot_download
            snapshot_download(repo_id=repo_id, revision=preview["revision"], local_dir=temporary, allow_patterns=patterns, cache_dir=HF_CACHE)
        source = temporary / candidate if candidate != "." else temporary
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        shutil.rmtree(temporary, ignore_errors=True)
        self.refresh()
        registered = self.register_local(str(destination), candidate or repo_id)
        record = self.get(registered["id"], allow_unready=True)
        record.source, record.repository, record.revision, record.license, record.author = "huggingface", repo_id, preview["revision"], preview["license"], preview["author"]
        record.license_reviewed = False
        self._save_state()
        return {"reused": False, "path": str(destination), "model": record.public()}

    def huggingface_status(self) -> dict[str, object]:
        return {**offline_status(), "cache_root": str(HF_CACHE.parent), "online_policy": "Owner-explicit Preview/Download only"}
