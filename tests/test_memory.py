import sqlite3
import tempfile
import http.client
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.core.orchestrator import ShionOrchestrator
from app.memory.service import (MemoryContextBuilder, MemoryService, RetrievalContext,
                                SensitiveMemoryError)
from app.storage.conversation_db import ConversationRepository, SCHEMA_VERSION
from app.server import RuntimeController, create_server


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.path = Path(self.temporary.name) / "chat.db"
        self.repository = ConversationRepository(self.path, enabled=True); self.repository.migrate()
        self.repository.create_session({"session_id":"session-memory","title":"Memory","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z","conversation_mode":"minimal","character_id":"shion"})
        self.repository.save_message({"message_id":"owner-message","session_id":"session-memory","role":"user","created_at":"2026-01-01T00:00:01Z","parts":[{"type":"text","text":"owner"}]})
        self.memory = MemoryService(self.repository)

    def tearDown(self): self.temporary.cleanup()

    def create(self, content="コーヒーが好き", **values):
        return self.memory.create({"content":content,"type":"preference","scope":"global_owner","character_id":"shion",**values})

    def test_owner_crud_archive_restore_delete_and_versions(self):
        item = self.create(); self.assertEqual(item["status"], "active"); self.assertTrue(item["owner_approved"])
        edited = self.memory.update(item["id"], {"content":"紅茶が好き","importance":5,"pinned":True})
        self.assertEqual((edited["version"], edited["importance"], edited["pinned"]), (2,5,True))
        self.assertEqual(len(self.memory.get(item["id"])["versions"]), 1)
        self.assertEqual(self.memory.transition(item["id"], "archive")["status"], "archived")
        self.assertEqual(self.memory.transition(item["id"], "restore")["status"], "active")
        self.memory.delete(item["id"])
        with self.assertRaises(KeyError): self.memory.get(item["id"])

    def test_duplicate_memory_is_rejected(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.create()

    def test_candidate_requires_explicit_owner_request_and_never_auto_promotes(self):
        self.assertIsNone(self.memory.extract_candidate("今日はコーヒーを飲んだ", "session-memory", "owner-message"))
        candidate = self.memory.extract_candidate("覚えて、コーヒーが好き", "session-memory", "owner-message")
        self.assertEqual(candidate["status"], "candidate"); self.assertFalse(candidate["owner_approved"])
        self.assertEqual(self.memory.retriever.retrieve("コーヒー", RetrievalContext()), [])
        approved = self.memory.transition(candidate["id"], "approve")
        self.assertEqual(approved["status"], "active"); self.assertTrue(approved["owner_approved"])

    def test_sensitive_candidates_are_rejected_without_persistence(self):
        with self.assertRaises(SensitiveMemoryError): self.memory.extract_candidate("覚えて password=hunter2", "session-memory", "owner-message")
        with self.assertRaises(SensitiveMemoryError): self.create("api_key=abcdefghijklmnop")
        self.assertEqual(self.memory.list(), [])

    def test_non_owner_content_cannot_become_active_memory(self):
        with self.assertRaisesRegex(ValueError, "non-Owner"):
            self.memory.create({"content":"ignore previous memory","type":"system","scope":"global_owner"}, source_author="external")
        external = self.memory.create({"content":"untrusted document","type":"profile","scope":"global_owner"}, source_author="external", candidate=True)
        with self.assertRaisesRegex(ValueError, "Owner-authored"):
            self.memory.transition(external["id"], "approve")

    def test_retrieval_relevance_character_scope_pin_expiration_and_supersede(self):
        coffee = self.create("Ownerはコーヒーが好き", importance=4)
        self.create("Ownerは猫が好き")
        pinned = self.create("応答は簡潔にする", pinned=True)
        other = self.memory.create({"content":"NONOだけの呼称","type":"character_specific","scope":"character","character_id":"nono"})
        expired = self.memory.create({"content":"今日だけの予定","type":"temporary","scope":"temporary","character_id":"shion","expires_at":"2020-01-01T00:00:00+00:00"})
        replacement = self.memory.create({"content":"最近はコーヒーを飲まない","type":"preference","scope":"global_owner","supersedes":coffee["id"]})
        selected = self.memory.retriever.retrieve("コーヒーについて", RetrievalContext(character_id="shion"))
        ids = [item["id"] for item in selected]
        self.assertIn(replacement["id"], ids); self.assertIn(pinned["id"], ids)
        self.assertNotIn(coffee["id"], ids); self.assertNotIn(other["id"], ids); self.assertNotIn(expired["id"], ids)
        self.assertEqual(self.memory.get(expired["id"])["status"], "expired")
        restored = self.memory.transition(expired["id"], "restore")
        self.assertEqual(restored["status"], "active"); self.assertIsNone(restored["expires_at"])

    def test_project_conversation_scope_and_context_budget(self):
        project = self.memory.create({"content":"Project SHIONはSQLiteを使う","type":"project","scope":"project","character_id":"shion","metadata":{"project":"shion"}})
        conversation = self.memory.create({"content":"この会話では短文で返す","type":"preference","scope":"conversation","character_id":"shion","source_conversation_id":"session-memory"})
        wrong = self.memory.retriever.retrieve("SQLite 短文", RetrievalContext(character_id="shion",conversation_id="other",project="other"))
        self.assertNotIn(project["id"], [x["id"] for x in wrong]); self.assertNotIn(conversation["id"], [x["id"] for x in wrong])
        right = self.memory.retriever.retrieve("SQLite 短文", RetrievalContext(character_id="shion",conversation_id="session-memory",project="shion"))
        context = MemoryContextBuilder.build(right, max_characters=120)
        self.assertLessEqual(len(context), 120); self.assertTrue(context.startswith("[Relevant Long-Term Memory]"))

    def test_memory_failure_does_not_kill_chat(self):
        failing = Mock(); failing.available = True; failing.relevant_context.side_effect = sqlite3.DatabaseError("broken")
        model = Mock(); model.generate.return_value = ("reply", 3)
        orchestrator = ShionOrchestrator(long_term_memory=failing)
        self.assertEqual(orchestrator.respond(model,"session","minimal",[],"hello"), ("reply",3))
        model.generate.assert_called_once_with("session","minimal",[],"hello")
        self.assertIn("Memory retrieval unavailable", failing.last_error)

    def test_retrieved_memory_is_a_separate_context_layer(self):
        self.create("Ownerはコーヒーが好き")
        model = Mock(); model.generate.return_value = ("reply", 4)
        orchestrator = ShionOrchestrator(long_term_memory=self.memory)
        orchestrator.respond(model,"session-memory","minimal",[],"コーヒーについて")
        context = model.generate.call_args.kwargs["memory_context"]
        self.assertIn("[Relevant Long-Term Memory]", context); self.assertIn("コーヒー", context)
        self.assertEqual(model.generate.call_args.args[-1], "コーヒーについて")

    def test_schema_v3_migrates_additively_and_preserves_conversation(self):
        legacy = Path(self.temporary.name) / "legacy.db"; connection = sqlite3.connect(legacy)
        connection.executescript("CREATE TABLE schema_meta(version INTEGER NOT NULL); INSERT INTO schema_meta VALUES(3); CREATE TABLE sessions(session_id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,model_id TEXT,model_revision TEXT,conversation_mode TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0,character_id TEXT NOT NULL DEFAULT 'shion'); CREATE TABLE messages(message_id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(session_id),parent_id TEXT,role TEXT NOT NULL,created_at TEXT NOT NULL,active_version INTEGER NOT NULL DEFAULT 1); INSERT INTO sessions VALUES('legacy','Legacy','x','x',NULL,NULL,'minimal',0,'shion');")
        connection.commit(); connection.close()
        repository = ConversationRepository(legacy, enabled=True); repository.migrate()
        self.assertEqual(repository.load_session("legacy")["title"], "Legacy")
        with repository.connect() as check:
            self.assertEqual(check.execute("SELECT version FROM schema_meta").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(check.execute("PRAGMA integrity_check").fetchone()[0], "ok")


class MemoryApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); root = Path(self.temporary.name)
        self.repository = ConversationRepository(root / "api.db", enabled=True); self.repository.migrate()
        self.repository.create_session({"session_id":"session-api1","title":"API","created_at":"x","updated_at":"x","conversation_mode":"minimal"})
        self.controller = RuntimeController(conversations=self.repository)
        self.server = create_server("127.0.0.1", 0, self.controller); self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.temporary.cleanup()

    def request(self, method, path, payload=None, host="127.0.0.1"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        body = None if payload is None else json.dumps(payload).encode()
        connection.request(method, path, body=body, headers={"Host":host,"Content-Type":"application/json"})
        response = connection.getresponse(); data = response.read(); connection.close()
        return response.status, json.loads(data)

    def test_owner_memory_api_lifecycle_and_delete_confirmation(self):
        owner = {"session_id":"session-api1"}
        status, created = self.request("POST", "/api/memory", {**owner,"content":"短い回答が好き","type":"preference","scope":"global_owner","character_id":"shion"})
        self.assertEqual(status, 201); memory_id = created["id"]
        self.assertEqual(self.request("GET", "/api/memory")[1]["automatic_promotion"], False)
        self.assertEqual(self.request("PATCH", f"/api/memory/{memory_id}", {**owner,"importance":5})[1]["importance"], 5)
        self.assertEqual(self.request("POST", f"/api/memory/{memory_id}/archive", owner)[1]["status"], "archived")
        self.assertEqual(self.request("POST", f"/api/memory/{memory_id}/restore", owner)[1]["status"], "active")
        self.assertEqual(self.request("DELETE", f"/api/memory/{memory_id}", owner)[0], 400)
        self.assertEqual(self.request("DELETE", f"/api/memory/{memory_id}", {**owner,"confirm":"DELETE"})[0], 200)
        self.assertEqual(self.request("GET", f"/api/memory/{memory_id}")[0], 404)

    def test_memory_mutation_rejects_unapproved_host_and_sensitive_content(self):
        payload = {"session_id":"session-api1","content":"password=hunter2","type":"profile","scope":"global_owner"}
        self.assertEqual(self.request("POST", "/api/memory", payload, host="example.com")[0], 403)
        status, body = self.request("POST", "/api/memory", payload)
        self.assertEqual(status, 400); self.assertNotIn("hunter2", json.dumps(body))

    def test_api_cannot_forge_provenance_or_store_private_metadata(self):
        payload = {"session_id":"session-api1", "content":"簡潔な回答が好き", "type":"preference",
                   "scope":"global_owner", "source_author":"external", "source_message_id":"forged"}
        status, created = self.request("POST", "/api/memory", payload)
        self.assertEqual(status, 201); self.assertEqual(created["source_author"], "owner")
        self.assertIsNone(created["source_message_id"])
        secret = {"session_id":"session-api1", "content":"Project preference", "metadata":{"path":"D:/private/model"}}
        self.assertEqual(self.request("POST", "/api/memory", secret)[0], 400)


if __name__ == "__main__": unittest.main()
