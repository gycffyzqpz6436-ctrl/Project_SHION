from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


HF_ACCESS_LOCK = threading.RLock()
HF_ROOT = Path(os.environ.get("SHION_DATA_ROOT", r"D:\AI\Project_SHION")) / "cache" / "huggingface"
ONLINE_KEYS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
CACHE_PATHS = {
    "HF_HOME": HF_ROOT,
    "HUGGINGFACE_HUB_CACHE": HF_ROOT / "hub",
    "TRANSFORMERS_CACHE": HF_ROOT / "transformers",
}


def _reset_huggingface_http_sessions() -> None:
    """Close cached hub clients across supported huggingface_hub versions."""
    from huggingface_hub.utils import _http
    reset = getattr(_http, "reset_sessions", None)
    if reset is not None:
        reset()
        return
    close = getattr(_http, "close_session", None)
    if close is not None:
        close()


def offline_status() -> dict[str, object]:
    env_values = {key: os.environ.get(key) for key in ONLINE_KEYS}
    constant = None
    if "huggingface_hub.constants" in sys.modules:
        from huggingface_hub import constants
        constant = bool(constants.HF_HUB_OFFLINE)
    enabled = any(str(value).strip().upper() in {"1", "ON", "YES", "TRUE"} for value in env_values.values()) or constant is True
    return {"enabled": enabled, "environment": env_values, "hub_constant": constant}


@contextmanager
def explicit_huggingface_online() -> Iterator[None]:
    """Temporarily enable HF access for an explicit Owner Preview/Download action."""
    with HF_ACCESS_LOCK:
        previous = {key: os.environ.get(key) for key in (*ONLINE_KEYS, *CACHE_PATHS)}
        for path in CACHE_PATHS.values():
            path.mkdir(parents=True, exist_ok=True)
        for key, path in CACHE_PATHS.items():
            os.environ[key] = str(path)
        for key in ONLINE_KEYS:
            os.environ.pop(key, None)

        from huggingface_hub import constants
        previous_constant = constants.HF_HUB_OFFLINE
        constants.HF_HUB_OFFLINE = False
        _reset_huggingface_http_sessions()
        try:
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            constants.HF_HUB_OFFLINE = previous_constant
            _reset_huggingface_http_sessions()
