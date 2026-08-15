import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.storage.conversation_db import ConversationRepository, SCHEMA_VERSION
from app.storage.paths import StoragePaths


class StoragePathTests(unittest.TestCase):
    def test_paths_resolve_below_explicit_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = StoragePaths.resolve(Path(temporary))
            paths.create_runtime_dirs()
            self.assertTrue(paths.conversation_db.parent.is_dir())
            self.assertTrue(paths.within(paths.conversation_db, paths.root))
            self.assertFalse(paths.within(paths.root.parent / "escape.db", paths.root))


class ConversationRepositoryTests(unittest.TestCase):
    def test_disabled_mode_does_not_create_db(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "chat.db"
            repository = ConversationRepository(path, enabled=False)
            with self.assertRaises(RuntimeError): repository.migrate()
            self.assertFalse(path.exists())

    def test_migration_session_rename_search_and_wal(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = ConversationRepository(Path(temporary) / "chat.db", enabled=True)
            repository.migrate()
            repository.create_session({
                "session_id": "s1", "title": "First chat", "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z", "model_id": "model", "model_revision": "abc",
                "conversation_mode": "minimal",
            })
            repository.rename_session("s1", "Renamed chat", "2026-01-02T00:00:00Z")
            repository.archive_session("s1", True, "2026-01-02T00:00:00Z")
            self.assertEqual(repository.list_sessions(), [])
            self.assertEqual(repository.list_sessions(include_archived=True)[0]["archived"], 1)
            repository.archive_session("s1", False, "2026-01-02T00:00:00Z")
            repository.save_message({"message_id": "m1", "session_id": "s1", "role": "assistant", "created_at": "2026-01-02T00:00:01Z", "parts": [{"type": "text", "text": "hello"}]})
            repository.add_response_version("m1", 2, [{"type": "text", "text": "hello again"}], {"created_at": "2026-01-02T00:00:02Z", "model_id": "model", "model_revision": "abc", "generation": {"latency_ms": 1}})
            repository.set_favorite("m1", True, "2026-01-02T00:00:03Z")
            repository.set_feedback("m1", "good", "2026-01-02T00:00:03Z")
            self.assertEqual(repository.search("Renamed")[0]["session_id"], "s1")
            loaded = repository.load_session("s1")
            self.assertEqual(loaded["character_id"], "shion")
            self.assertEqual(loaded["messages"][0]["parts"][0]["text"], "hello")
            with closing(repository.connect()) as connection:
                self.assertEqual(connection.execute("SELECT version FROM schema_meta").fetchone()[0], SCHEMA_VERSION)
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_japanese_message_search_and_rename_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = ConversationRepository(Path(temporary) / "chat.db", enabled=True)
            repository.migrate()
            repository.create_session({
                "session_id": "s1", "title": "New Chat", "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z", "conversation_mode": "neutral",
            })
            repository.save_message({"message_id": "m1", "session_id": "s1", "role": "user",
                                     "created_at": "2026-01-01T00:00:01Z",
                                     "parts": [{"type": "text", "text": "日本語の検索対象です"}]})
            self.assertEqual(repository.list_sessions("検索対象")[0]["session_id"], "s1")
            repository.rename_session("s1", "<script>alert(1)</script> & friends", "2026-01-02T00:00:00Z")
            self.assertEqual(repository.load_session("s1")["title"], "<script>alert(1)</script> & friends")
            with self.assertRaises(ValueError):
                repository.rename_session("s1", "   ", "2026-01-02T00:00:01Z")

    def test_incompatible_schema_stops_migration_without_rewriting_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "chat.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE schema_meta(version INTEGER NOT NULL)")
            connection.execute("INSERT INTO schema_meta VALUES(999)")
            connection.commit(); connection.close()
            repository = ConversationRepository(path, enabled=True)
            with self.assertRaisesRegex(RuntimeError, "unsupported conversation schema"):
                repository.migrate()
            with closing(sqlite3.connect(path)) as check:
                self.assertEqual(check.execute("SELECT version FROM schema_meta").fetchone()[0], 999)

    def test_schema_v2_additively_binds_existing_sessions_to_shion(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "chat.db"
            connection = sqlite3.connect(path)
            connection.executescript("CREATE TABLE schema_meta(version INTEGER NOT NULL); INSERT INTO schema_meta VALUES(2); CREATE TABLE sessions(session_id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,model_id TEXT,model_revision TEXT,conversation_mode TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0);")
            connection.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?)", ("legacy", "Legacy", "x", "x", None, None, "minimal", 0))
            connection.commit(); connection.close()
            repository = ConversationRepository(path, enabled=True); repository.migrate()
            self.assertEqual(repository.load_session("legacy")["character_id"], "shion")

    def test_schema_v4_voice_artifacts_migrate_into_persistent_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "chat.db"; repository = ConversationRepository(path, enabled=True); repository.migrate()
            repository.create_session({"session_id":"legacy","title":"Legacy","created_at":"x","updated_at":"x","conversation_mode":"minimal"})
            repository.save_message({"message_id":"assistant","session_id":"legacy","role":"assistant","created_at":"x","parts":[{"type":"text","text":"hello"}]})
            with closing(repository.connect()) as connection:
                connection.execute("DROP TABLE voice_artifacts")
                connection.execute("""CREATE TABLE voice_artifacts(
                    artifact_id TEXT PRIMARY KEY,message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
                    response_version INTEGER NOT NULL,voice_model_id TEXT NOT NULL,voice_revision TEXT,voice_preset_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,duration REAL NOT NULL,relative_path TEXT NOT NULL UNIQUE,attempt INTEGER NOT NULL,
                    generation_json TEXT NOT NULL,UNIQUE(message_id,response_version,voice_preset_id,attempt))""")
                connection.execute("INSERT INTO voice_artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                   ("artifact","assistant",1,"nene_v3_candidate","rev","SHION Default","x",1.0,"legacy.wav",1,"{}"))
                connection.execute("UPDATE schema_meta SET version=4"); connection.commit()
            repository.migrate(); migrated = repository.get_voice_artifact("artifact")
            self.assertEqual(migrated["source_type"], "message")
            self.assertEqual(migrated["character_id"], "shion")
            self.assertEqual(migrated["session_id"], "legacy")

    def test_transaction_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = ConversationRepository(Path(temporary) / "chat.db", enabled=True)
            repository.migrate()
            with self.assertRaises(sqlite3.IntegrityError):
                repository.create_session({
                    "session_id": "bad", "title": None, "created_at": "x", "updated_at": "x",
                    "conversation_mode": "minimal",
                })
            with closing(repository.connect()) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
