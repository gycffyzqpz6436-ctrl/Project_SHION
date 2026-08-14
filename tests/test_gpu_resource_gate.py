import threading
import time
import unittest
from unittest.mock import Mock

from app.core.gpu_resource_gate import (GpuResourceGate, ResourceGateCancelled,
                                        ResourceGateFull, ResourceGateTimeout)
from app.core.shion_runtime import ShionRuntime
from app.core.state import RuntimeState


class GpuResourceGateTests(unittest.TestCase):
    def gate(self, **options):
        return GpuResourceGate(lambda: True, settle_seconds=0, timeout_seconds=.5, **options)

    @staticmethod
    def wait_for(predicate, timeout=.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.005)
        raise AssertionError("condition not reached")

    def test_llm_generation_blocks_voice_until_release(self):
        gate = self.gate(); gate.begin_llm(); started = threading.Event(); result = []
        thread = threading.Thread(target=lambda: result.append(gate.submit_voice("v", {}, lambda: started.set() or "voice")))
        thread.start(); self.wait_for(lambda: gate.status()["waiting"] == 1)
        self.assertFalse(started.is_set())
        gate.end_llm(); thread.join(1)
        self.assertEqual(result, ["voice"])

    def test_voice_queue_is_fifo(self):
        gate = self.gate(); gate.begin_llm(); order = []
        threads = []
        for index in range(3):
            thread = threading.Thread(target=lambda value=index: gate.submit_voice(value, {}, lambda: order.append(value)))
            threads.append(thread); thread.start()
            self.wait_for(lambda expected=index + 1: gate.status()["waiting"] == expected)
        gate.end_llm()
        for thread in threads: thread.join(1)
        self.assertEqual(order, [0, 1, 2])

    def test_duplicate_request_shares_one_execution(self):
        gate = self.gate(); gate.begin_llm(); calls = []; results = []
        work = lambda: calls.append("called") or "shared"
        threads = [threading.Thread(target=lambda: results.append(gate.submit_voice(("m", 1, "p"), {}, work))) for _ in range(2)]
        for thread in threads: thread.start()
        self.wait_for(lambda: gate.status()["waiting"] == 1)
        gate.end_llm()
        for thread in threads: thread.join(1)
        self.assertEqual(calls, ["called"])
        self.assertEqual(results, ["shared", "shared"])

    def test_waiting_request_can_be_cancelled(self):
        gate = self.gate(); gate.begin_llm(); errors = []
        thread = threading.Thread(target=lambda: self._capture(errors, lambda: gate.submit_voice(
            "v", {"session_id": "session-1", "message_id": "message-1", "response_version": 2}, lambda: None)))
        thread.start(); self.wait_for(lambda: gate.status()["waiting"] == 1)
        self.assertEqual(gate.cancel(session_id="session-1", message_id="message-1", response_version=2), 1)
        thread.join(1); gate.end_llm()
        self.assertIsInstance(errors[0], ResourceGateCancelled)

    def test_waiting_request_times_out(self):
        gate = self.gate(); gate.begin_llm(); errors = []
        thread = threading.Thread(target=lambda: self._capture(errors, lambda: gate.submit_voice(
            "v", {}, lambda: None, timeout_seconds=.04)))
        thread.start(); thread.join(1); gate.end_llm()
        self.assertIsInstance(errors[0], ResourceGateTimeout)

    def test_queue_limit_is_bounded(self):
        gate = self.gate(queue_limit=1); gate.begin_llm(); errors = []
        thread = threading.Thread(target=lambda: self._capture(errors, lambda: gate.submit_voice("first", {}, lambda: None)))
        thread.start(); self.wait_for(lambda: gate.status()["waiting"] == 1)
        with self.assertRaises(ResourceGateFull):
            gate.submit_voice("second", {}, lambda: None)
        gate.cancel(); thread.join(1); gate.end_llm()

    def test_generation_failure_releases_llm_gate(self):
        registry = Mock(); registry.public_models.return_value = []
        runtime = ShionRuntime(registry); runtime.runtime = Mock(); runtime.state = RuntimeState.READY
        runtime.orchestrator.respond = Mock(side_effect=RuntimeError("generation failed"))
        runtime.gpu_gate = self.gate()
        with self.assertRaisesRegex(RuntimeError, "generation failed"):
            runtime.chat("session", "minimal", "hello")
        self.assertEqual(runtime.state, RuntimeState.READY)
        self.assertEqual(runtime.gpu_gate.submit_voice("voice", {}, lambda: "released"), "released")

    @staticmethod
    def _capture(errors, function):
        try:
            function()
        except BaseException as error:
            errors.append(error)


if __name__ == "__main__":
    unittest.main()
