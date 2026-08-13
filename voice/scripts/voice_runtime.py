from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "prototype_v0_1.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    required = ("external_root", "runtime_source", "output_dir", "model", "generation")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing configuration keys: {', '.join(missing)}")
    return config


def configure_external_environment(config: dict[str, Any]) -> None:
    root = Path(os.environ.get("SHION_DATA_ROOT", config["external_root"]))
    locations = {
        "HF_HOME": root / "cache" / "huggingface",
        "HUGGINGFACE_HUB_CACHE": root / "cache" / "huggingface" / "hub",
        "TRANSFORMERS_CACHE": root / "cache" / "huggingface" / "transformers",
        "TORCH_HOME": root / "cache" / "torch",
        "NLTK_DATA": root / "cache" / "nltk",
        "TEMP": root / "temp",
        "TMP": root / "temp",
    }
    for key, value in locations.items():
        value.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(value)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    runtime = Path(config["runtime_source"])
    if not runtime.is_dir():
        raise FileNotFoundError(f"Style-Bert-VITS2 source is missing: {runtime}")
    sys.path.insert(0, str(runtime))


def validate_external_paths(config: dict[str, Any]) -> None:
    root = Path(config["external_root"]).resolve()
    paths = [
        Path(config["runtime_source"]),
        Path(config["output_dir"]),
        *(Path(config["model"][key]) for key in ("checkpoint", "config", "style_vectors")),
    ]
    for path in paths:
        resolved = path.resolve()
        if root != resolved and root not in resolved.parents:
            raise ValueError(f"Path escapes external_root: {resolved}")
    for key in ("checkpoint", "config", "style_vectors"):
        path = Path(config["model"][key])
        if not path.is_file():
            raise FileNotFoundError(f"Required model file is missing: {path}")
