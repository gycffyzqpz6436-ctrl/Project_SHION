from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Hashable, TypeVar


T = TypeVar("T")


class ResourceGateFull(RuntimeError):
    pass


class ResourceGateTimeout(RuntimeError):
    pass


class ResourceGateCancelled(RuntimeError):
    pass


@dataclass
class _VoiceRequest:
    key: Hashable
    identity: dict[str, object]
    deadline: float
    work: Callable[[], object]
    done: threading.Event = field(default_factory=threading.Event)
    state: str = "WAITING_FOR_GPU"
    result: object | None = None
    error: BaseException | None = None


class GpuResourceGate:
    """Serialize LLM and Voice GPU ownership without using VRAM as a gate."""

    def __init__(self, runtime_ready: Callable[[], bool], queue_limit: int = 8,
                 timeout_seconds: float = 120.0, settle_seconds: float = 0.35) -> None:
        if queue_limit < 1 or timeout_seconds <= 0 or settle_seconds < 0:
            raise ValueError("invalid GPU resource gate limits")
        self.runtime_ready = runtime_ready
        self.queue_limit = queue_limit
        self.timeout_seconds = timeout_seconds
        self.settle_seconds = settle_seconds
        self._condition = threading.Condition()
        self._queue: deque[_VoiceRequest] = deque()
        self._requests: dict[Hashable, _VoiceRequest] = {}
        self._llm_active = False
        self._llm_waiting = 0
        self._voice_active = False
        self._last_llm_release = 0.0

    def begin_llm(self) -> None:
        with self._condition:
            self._llm_waiting += 1
            try:
                while self._llm_active or self._voice_active:
                    self._condition.wait()
                self._llm_active = True
            finally:
                self._llm_waiting -= 1

    def end_llm(self) -> None:
        with self._condition:
            self._llm_active = False
            self._last_llm_release = time.monotonic()
            self._condition.notify_all()

    def submit_voice(self, key: Hashable, identity: dict[str, object], work: Callable[[], T],
                     timeout_seconds: float | None = None) -> T:
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        if timeout <= 0:
            raise ValueError("Voice queue timeout must be positive")
        deadline = time.monotonic() + timeout
        with self._condition:
            request = self._requests.get(key)
            if request is None:
                if len(self._queue) >= self.queue_limit:
                    raise ResourceGateFull("Voice queue is full")
                request = _VoiceRequest(key, dict(identity), deadline, work)
                self._requests[key] = request
                self._queue.append(request)
                self._condition.notify_all()

        self._await_or_execute(request)
        if request.error is not None:
            raise request.error
        return request.result  # type: ignore[return-value]

    def _await_or_execute(self, request: _VoiceRequest) -> None:
        while not request.done.is_set():
            execute = False
            with self._condition:
                if request.done.is_set():
                    break
                remaining = request.deadline - time.monotonic()
                if remaining <= 0:
                    self._finish_locked(request, error=ResourceGateTimeout("Voice request timed out while waiting for GPU"))
                    break
                settled = time.monotonic() - self._last_llm_release >= self.settle_seconds
                if (self._queue and self._queue[0] is request and not self._llm_active
                        and not self._llm_waiting and not self._voice_active
                        and self.runtime_ready() and settled):
                    self._queue.popleft()
                    self._voice_active = True
                    request.state = "GENERATING"
                    execute = True
                else:
                    settle_wait = max(0.0, self.settle_seconds - (time.monotonic() - self._last_llm_release))
                    self._condition.wait(min(remaining, settle_wait or 0.1))
            if execute:
                try:
                    result = request.work()
                except BaseException as error:
                    with self._condition:
                        self._voice_active = False
                        self._finish_locked(request, error=error)
                else:
                    with self._condition:
                        self._voice_active = False
                        self._finish_locked(request, result=result)

    def _finish_locked(self, request: _VoiceRequest, result: object | None = None,
                       error: BaseException | None = None) -> None:
        try:
            self._queue.remove(request)
        except ValueError:
            pass
        request.result, request.error = result, error
        request.state = "CANCELLED" if isinstance(error, ResourceGateCancelled) else "DONE"
        self._requests.pop(request.key, None)
        request.done.set()
        self._condition.notify_all()

    def cancel(self, *, session_id: str | None = None, message_id: str | None = None,
               response_version: int | None = None, request_id: str | None = None) -> int:
        cancelled = 0
        with self._condition:
            for request in list(self._queue):
                identity = request.identity
                if session_id is not None and identity.get("session_id") != session_id:
                    continue
                if message_id is not None and identity.get("message_id") != message_id:
                    continue
                if response_version is not None and identity.get("response_version") != response_version:
                    continue
                if request_id is not None and identity.get("request_id") != request_id:
                    continue
                self._finish_locked(request, error=ResourceGateCancelled("Voice request cancelled"))
                cancelled += 1
        return cancelled

    def status(self) -> dict[str, object]:
        with self._condition:
            waiting = len(self._queue)
            state = "GENERATING" if self._voice_active else "WAITING_FOR_GPU" if waiting else "READY"
            return {"state": state, "waiting": waiting, "limit": self.queue_limit,
                    "timeout_seconds": self.timeout_seconds, "llm_active": self._llm_active}
