from __future__ import annotations

import logging
import threading
import traceback
from pathlib import Path
from typing import Callable

from app.core.orchestrator import ShionOrchestrator
from app.core.session import SessionStore
from app.core.state import RuntimeState
from app.models.loader import load_conversation_model
from app.models.registry import ModelRegistry


LOG = logging.getLogger("shion_web")


class ShionRuntime:
    """Application runtime coordinating models, sessions and future capabilities."""

    def __init__(self, registry: ModelRegistry, model_factory: Callable = load_conversation_model) -> None:
        self.state = RuntimeState.STARTING
        self.runtime = None
        self.registry = registry
        self.model_factory = model_factory
        self.current_alias = None
        self.sessions = SessionStore()
        self.orchestrator = ShionOrchestrator()
        self.state_lock = threading.Lock()

    @property
    def histories(self) -> dict:
        """Compatibility view for existing callers and tests."""
        return self.sessions.histories

    def public_models(self) -> list[dict]:
        return self.registry.public_models()

    def load(self, common: Path, alias: str, adapter: Path | None = None) -> None:
        spec = self.registry.available(alias)
        self.state = RuntimeState.LOADING

        def worker() -> None:
            try:
                old_runtime = self.runtime
                self.runtime = None
                if old_runtime is not None:
                    old_runtime.close()
                self.sessions.clear()
                self.runtime = self.model_factory(common, alias, spec, adapter)
                self.current_alias = alias
                self.state = RuntimeState.READY
            except Exception:
                self.state = RuntimeState.ERROR
                LOG.error("Model loading failed\n%s", traceback.format_exc())

        threading.Thread(target=worker, name="model-loader", daemon=True).start()

    def status(self) -> dict:
        result = {
            "state": str(self.state),
            "models": self.public_models(),
            "capabilities": self.orchestrator.capability_status(),
        }
        if self.runtime is not None:
            result.update(self.runtime.status())
        return result

    def chat(self, session_id: str, mode: str, message: str) -> dict:
        if self.state != RuntimeState.READY or self.runtime is None:
            raise RuntimeError("モデルはまだ準備中です。")
        history = self.sessions.history(session_id, mode)
        self.state = RuntimeState.GENERATING
        try:
            response, context_tokens = self.orchestrator.respond(
                self.runtime, session_id, mode, history, message
            )
            history.extend(({"role": "user", "content": message}, {"role": "assistant", "content": response}))
            return {"response": response, "context_tokens": context_tokens}
        finally:
            self.state = RuntimeState.READY

    def cancel(self, session_id: str) -> bool:
        if self.state != RuntimeState.GENERATING or self.runtime is None:
            return False
        return self.runtime.cancel(session_id)

    def reset(self, session_id: str) -> None:
        self.sessions.reset(session_id)
        if self.runtime is not None:
            self.runtime.reset(session_id)

    def switch(self, common: Path, alias: str, session_id: str) -> None:
        with self.state_lock:
            if self.state != RuntimeState.READY:
                raise RuntimeError("model is busy")
            if alias == self.current_alias:
                self.reset(session_id)
                return
            self.load(common, alias)
