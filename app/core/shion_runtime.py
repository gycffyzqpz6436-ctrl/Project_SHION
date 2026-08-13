from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.orchestrator import ShionOrchestrator
from app.core.session import SessionStore
from app.core.state import RuntimeState
from app.models.loader import load_conversation_model
from app.models.registry import ModelRegistry
from app.storage.conversation_db import ConversationRepository


LOG = logging.getLogger("shion_web")


def conversation_title(message: str, limit: int = 24) -> str:
    """Create a cheap, deterministic Japanese-friendly title from the first message."""
    compact = " ".join(message.replace("\u3000", " ").split()).strip()
    compact = compact.lstrip("#*-・• ").rstrip("。！？!?.,、 ")
    for separator in ("。", "！", "？", "!", "?", "\n"):
        compact = compact.split(separator, 1)[0].strip()
    if not compact:
        return "New Chat"
    return compact if len(compact) <= limit else f"{compact[:limit - 1].rstrip()}…"


class ShionRuntime:
    """Application runtime coordinating models, sessions and future capabilities."""

    def __init__(self, registry: ModelRegistry, model_factory: Callable = load_conversation_model,
                 conversations: ConversationRepository | None = None) -> None:
        self.state = RuntimeState.STARTING
        self.runtime = None
        self.registry = registry
        self.model_factory = model_factory
        self.current_alias = None
        self.sessions = SessionStore()
        self.orchestrator = ShionOrchestrator()
        self.state_lock = threading.Lock()
        self.conversations = conversations
        self.persistence_error: str | None = None

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
            "history": {"state": "PERSISTENT" if self.conversations and not self.persistence_error else
                        ("UNAVAILABLE" if self.persistence_error else "EPHEMERAL"), "error": self.persistence_error},
        }
        if self.runtime is not None:
            result.update(self.runtime.status())
        return result

    def chat(self, session_id: str, mode: str, message: str, persist: bool = True) -> dict:
        if self.state != RuntimeState.READY or self.runtime is None:
            raise RuntimeError("モデルはまだ準備中です。")
        history = self._history(session_id, mode)
        self.state = RuntimeState.GENERATING
        started = time.perf_counter()
        try:
            response, context_tokens = self.orchestrator.respond(
                self.runtime, session_id, mode, history, message
            )
            user_id, assistant_id = str(uuid.uuid4()), str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            history.extend(({"role": "user", "content": message}, {"role": "assistant", "content": response}))
            runtime_status = self.runtime.status()
            result = {
                "response": response,
                "context_tokens": context_tokens,
                "message_id": assistant_id,
                "user_message_id": user_id,
                "created_at": created_at,
                "model": {
                    "id": runtime_status.get("repo_id", self.current_alias),
                    "revision": runtime_status.get("revision"),
                    "alias": self.current_alias,
                },
                "mode": mode,
                "generation": {
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                    "context_tokens": context_tokens,
                },
            }
            if persist:
                self._persist_turn(session_id, mode, message, result)
            return result
        finally:
            self.state = RuntimeState.READY

    def regenerate(self, session_id: str, mode: str, message_id: str | None = None) -> dict:
        history = self._history(session_id, mode)
        if len(history) < 2 or history[-2].get("role") != "user" or history[-1].get("role") != "assistant":
            raise ValueError("there is no assistant response to regenerate")
        user_message = str(history[-2].get("content", ""))
        del history[-2:]
        result = self.chat(session_id, mode, user_message, persist=False)
        if self.conversations and message_id:
            try:
                versions = self.conversations.load_response_versions(message_id)
                version = len(versions) + 1
                self.conversations.add_response_version(message_id, version, [{"type": "text", "text": result["response"]}], {
                    "created_at": result["created_at"], "model_id": result["model"]["id"],
                    "model_revision": result["model"]["revision"], "generation": result["generation"]})
                result["message_id"] = message_id
                result["version"] = version
            except Exception as error:
                self.persistence_error = f"Regenerate persistence failed: {error}"
        return result

    def select_response(self, session_id: str, mode: str, response: str) -> None:
        if not response or len(response) > 20_000:
            raise ValueError("invalid response version")
        history = self.sessions.history(session_id, mode)
        if not history or history[-1].get("role") != "assistant":
            raise ValueError("there is no assistant response to select")
        history[-1] = {"role": "assistant", "content": response}

    def _history(self, session_id: str, mode: str) -> list[dict]:
        key = (session_id, mode)
        if key not in self.sessions.histories and self.conversations:
            try:
                loaded = self.conversations.load_session(session_id)
                projection = []
                for item in loaded["messages"]:
                    text = "\n".join(part.get("text", "") for part in item["parts"] if part.get("type") == "text")
                    if item["role"] in {"user", "assistant"}: projection.append({"role": item["role"], "content": text})
                self.sessions.histories[key] = projection
            except KeyError:
                pass
            except Exception as error:
                self.persistence_error = f"History read failed: {error}"
        return self.sessions.history(session_id, mode)

    def _persist_turn(self, session_id: str, mode: str, message: str, result: dict) -> None:
        if not self.conversations: return
        try:
            session = self.conversations.load_session(session_id)
            # Rename wins permanently: automatic naming is applied once, and only
            # while the canonical title still has its untouched sentinel value.
            title = session["title"] if session["title"] != "New Chat" else conversation_title(message)
            model = result["model"]
            self.conversations.save_turn(
                {"session_id": session_id, "title": title, "updated_at": result["created_at"],
                 "model_id": model["id"], "model_revision": model["revision"], "conversation_mode": mode},
                {"message_id": result["user_message_id"], "session_id": session_id, "parent_id": None,
                 "role": "user", "created_at": result["created_at"], "parts": [{"type": "text", "text": message}]},
                {"message_id": result["message_id"], "session_id": session_id, "parent_id": result["user_message_id"],
                 "role": "assistant", "created_at": result["created_at"], "parts": [{"type": "text", "text": result["response"]}],
                 "generation": result["generation"]})
            result["session_title"] = title
            self.persistence_error = None
        except Exception as error:
            self.persistence_error = f"Conversation saved only ephemerally: {error}"

    def create_persistent_session(self, session_id: str, mode: str, model_id: str | None = None, revision: str | None = None) -> dict:
        if not self.conversations: raise RuntimeError("persistent history unavailable")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        session = {"session_id": session_id, "title": "New Chat", "created_at": now, "updated_at": now,
                   "model_id": model_id, "model_revision": revision, "conversation_mode": mode}
        self.conversations.create_session(session)
        return session

    def cancel(self, session_id: str) -> bool:
        if self.state != RuntimeState.GENERATING or self.runtime is None:
            return False
        return self.runtime.cancel(session_id)

    def reset(self, session_id: str) -> None:
        self.sessions.reset(session_id)
        if self.runtime is not None:
            self.runtime.reset(session_id)

    def close(self) -> None:
        """Release model resources and in-memory sessions during graceful shutdown."""
        runtime, self.runtime = self.runtime, None
        self.sessions.clear()
        if runtime is not None:
            runtime.close()
        self.current_alias = None
        self.state = RuntimeState.STARTING

    def switch(self, common: Path, alias: str, session_id: str) -> None:
        with self.state_lock:
            if self.state != RuntimeState.READY:
                raise RuntimeError("model is busy")
            if alias == self.current_alias:
                return
            self.load(common, alias)
