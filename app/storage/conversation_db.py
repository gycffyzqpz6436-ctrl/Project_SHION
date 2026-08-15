"""Schema-versioned SQLite conversation-history repository."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 5
SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta(version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
 session_id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, model_id TEXT, model_revision TEXT,
 conversation_mode TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
 character_id TEXT NOT NULL DEFAULT 'shion'
);
CREATE TABLE IF NOT EXISTS messages(
 message_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
 parent_id TEXT REFERENCES messages(message_id), role TEXT NOT NULL,
 created_at TEXT NOT NULL, active_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS message_parts(
 part_id INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, part_type TEXT NOT NULL, payload_json TEXT NOT NULL,
 UNIQUE(message_id, ordinal)
);
CREATE TABLE IF NOT EXISTS response_versions(
 message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
 version INTEGER NOT NULL, content_json TEXT NOT NULL, model_id TEXT, model_revision TEXT,
 generation_json TEXT, created_at TEXT NOT NULL, PRIMARY KEY(message_id, version)
);
CREATE TABLE IF NOT EXISTS favorites(
 message_id TEXT PRIMARY KEY REFERENCES messages(message_id) ON DELETE CASCADE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback(
 message_id TEXT PRIMARY KEY REFERENCES messages(message_id) ON DELETE CASCADE,
 rating TEXT NOT NULL CHECK(rating IN ('good','bad')), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session_created ON messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE TABLE IF NOT EXISTS voice_artifacts(
 artifact_id TEXT PRIMARY KEY,
 message_id TEXT REFERENCES messages(message_id) ON DELETE SET NULL,
 response_version INTEGER, session_id TEXT REFERENCES sessions(session_id) ON DELETE SET NULL,
 source_type TEXT NOT NULL DEFAULT 'message' CHECK(source_type IN ('message','lab')),
 source_text TEXT NOT NULL DEFAULT '', tts_text TEXT NOT NULL DEFAULT '',
 character_id TEXT NOT NULL DEFAULT 'shion', voice_model_id TEXT NOT NULL, voice_revision TEXT,
 voice_style TEXT NOT NULL DEFAULT '', voice_preset_id TEXT NOT NULL,
 parameters_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
 latency REAL NOT NULL DEFAULT 0, duration REAL NOT NULL, file_size INTEGER NOT NULL DEFAULT 0,
 favorite INTEGER NOT NULL DEFAULT 0 CHECK(favorite IN (0,1)),
 relative_path TEXT NOT NULL UNIQUE, attempt INTEGER NOT NULL, generation_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_voice_artifacts_message ON voice_artifacts(message_id,response_version);
CREATE INDEX IF NOT EXISTS idx_voice_artifacts_created ON voice_artifacts(created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_voice_artifacts_attempt ON voice_artifacts(message_id,response_version,voice_preset_id,attempt) WHERE message_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS pronunciation_rules(
 rule_id TEXT PRIMARY KEY, original_text TEXT NOT NULL, replacement TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
 character_id TEXT NOT NULL DEFAULT 'shion', priority INTEGER NOT NULL DEFAULT 100,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(character_id,original_text)
);
CREATE INDEX IF NOT EXISTS idx_pronunciation_character ON pronunciation_rules(character_id,enabled,priority DESC,created_at);
CREATE TABLE IF NOT EXISTS memories(
 id TEXT PRIMARY KEY,
 type TEXT NOT NULL CHECK(type IN ('preference','profile','project','relationship','decision','temporary','character_specific','system')),
 character_id TEXT NOT NULL DEFAULT 'shion',
 scope TEXT NOT NULL CHECK(scope IN ('global_owner','character','project','conversation','temporary')),
 content TEXT NOT NULL,
 normalized_content TEXT NOT NULL,
 source_conversation_id TEXT REFERENCES sessions(session_id) ON DELETE SET NULL,
 source_message_id TEXT REFERENCES messages(message_id) ON DELETE SET NULL,
 source_author TEXT NOT NULL CHECK(source_author IN ('owner','assistant','external','system')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_used_at TEXT,
 expires_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('candidate','active','archived','rejected','expired')),
 confidence REAL NOT NULL DEFAULT 0 CHECK(confidence BETWEEN 0 AND 1),
 importance INTEGER NOT NULL DEFAULT 3 CHECK(importance BETWEEN 1 AND 5),
 owner_approved INTEGER NOT NULL DEFAULT 0 CHECK(owner_approved IN (0,1)),
 pinned INTEGER NOT NULL DEFAULT 0 CHECK(pinned IN (0,1)),
 retrieval_count INTEGER NOT NULL DEFAULT 0,
 metadata_json TEXT NOT NULL DEFAULT '{}',
 version INTEGER NOT NULL DEFAULT 1,
 supersedes TEXT REFERENCES memories(id) ON DELETE SET NULL,
 superseded_by TEXT REFERENCES memories(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_status_scope ON memories(status,scope,character_id);
CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source_conversation_id,source_message_id);
CREATE TABLE IF NOT EXISTS memory_versions(
 memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
 version INTEGER NOT NULL, content TEXT NOT NULL, normalized_content TEXT NOT NULL,
 type TEXT NOT NULL, character_id TEXT NOT NULL, scope TEXT NOT NULL,
 status TEXT NOT NULL, importance INTEGER NOT NULL, pinned INTEGER NOT NULL,
 metadata_json TEXT NOT NULL, changed_at TEXT NOT NULL,
 PRIMARY KEY(memory_id,version)
);
CREATE TABLE IF NOT EXISTS memory_settings(
 setting_key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
"""


class ConversationRepository:
    def __init__(self, path: Path, enabled: bool = False) -> None:
        self.path = path
        self.enabled = enabled

    def connect(self) -> sqlite3.Connection:
        if not self.enabled:
            raise RuntimeError("persistent conversation history is disabled")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def migrate(self) -> None:
        with closing(self.connect()) as connection:
            exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_meta'").fetchone()
            if exists:
                row = connection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
                if row and row["version"] not in {1, 2, 3, 4, SCHEMA_VERSION}:
                    raise RuntimeError(f"unsupported conversation schema version: {row['version']}")
        with self.transaction() as connection:
            connection.executescript(SCHEMA)
            row = connection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
            elif row["version"] in {1, 2, 3, 4}:
                columns = {item["name"] for item in connection.execute("PRAGMA table_info(sessions)")}
                if "character_id" not in columns:
                    connection.execute("ALTER TABLE sessions ADD COLUMN character_id TEXT NOT NULL DEFAULT 'shion'")
                voice_columns = {item["name"] for item in connection.execute("PRAGMA table_info(voice_artifacts)")}
                if "source_type" not in voice_columns:
                    connection.execute("ALTER TABLE voice_artifacts RENAME TO voice_artifacts_v4")
                    connection.executescript("""
                    CREATE TABLE voice_artifacts(
                     artifact_id TEXT PRIMARY KEY,
                     message_id TEXT REFERENCES messages(message_id) ON DELETE SET NULL,
                     response_version INTEGER, session_id TEXT REFERENCES sessions(session_id) ON DELETE SET NULL,
                     source_type TEXT NOT NULL DEFAULT 'message' CHECK(source_type IN ('message','lab')),
                     source_text TEXT NOT NULL DEFAULT '', tts_text TEXT NOT NULL DEFAULT '',
                     character_id TEXT NOT NULL DEFAULT 'shion', voice_model_id TEXT NOT NULL, voice_revision TEXT,
                     voice_style TEXT NOT NULL DEFAULT '', voice_preset_id TEXT NOT NULL,
                     parameters_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
                     latency REAL NOT NULL DEFAULT 0, duration REAL NOT NULL, file_size INTEGER NOT NULL DEFAULT 0,
                     favorite INTEGER NOT NULL DEFAULT 0 CHECK(favorite IN (0,1)),
                     relative_path TEXT NOT NULL UNIQUE, attempt INTEGER NOT NULL, generation_json TEXT NOT NULL
                    );
                    INSERT INTO voice_artifacts(
                     artifact_id,message_id,response_version,session_id,source_type,character_id,
                     voice_model_id,voice_revision,voice_preset_id,created_at,duration,relative_path,attempt,generation_json
                    ) SELECT v.artifact_id,v.message_id,v.response_version,m.session_id,'message',COALESCE(s.character_id,'shion'),
                     v.voice_model_id,v.voice_revision,v.voice_preset_id,v.created_at,v.duration,v.relative_path,v.attempt,v.generation_json
                     FROM voice_artifacts_v4 v LEFT JOIN messages m ON m.message_id=v.message_id
                     LEFT JOIN sessions s ON s.session_id=m.session_id;
                    DROP TABLE voice_artifacts_v4;
                    CREATE INDEX idx_voice_artifacts_message ON voice_artifacts(message_id,response_version);
                    CREATE INDEX idx_voice_artifacts_created ON voice_artifacts(created_at DESC);
                    CREATE UNIQUE INDEX idx_voice_artifacts_attempt ON voice_artifacts(message_id,response_version,voice_preset_id,attempt) WHERE message_id IS NOT NULL;
                    """)
                connection.execute("UPDATE schema_meta SET version=?", (SCHEMA_VERSION,))
            connection.execute(
                "INSERT OR IGNORE INTO memory_settings(setting_key,value_json,updated_at) VALUES('automatic_promotion','false',datetime('now'))"
            )

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_session(self, session: dict) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO sessions(session_id,title,created_at,updated_at,model_id,model_revision,conversation_mode,character_id) VALUES(?,?,?,?,?,?,?,?)",
                (session["session_id"], session["title"], session["created_at"], session["updated_at"],
                 session.get("model_id"), session.get("model_revision"), session["conversation_mode"], session.get("character_id", "shion")),
            )

    def list_sessions(self, query: str = "", include_archived: bool = False, limit: int = 100) -> list[dict]:
        with closing(self.connect()) as connection:
            archived = "" if include_archived else "s.archived=0 AND "
            pattern = f"%{query.strip()}%"
            rows = connection.execute(
                "SELECT DISTINCT s.* FROM sessions s LEFT JOIN messages m ON m.session_id=s.session_id "
                "LEFT JOIN message_parts p ON p.message_id=m.message_id "
                f"WHERE {archived}(?='' OR s.title LIKE ? OR p.payload_json LIKE ?) "
                "ORDER BY s.updated_at DESC LIMIT ?",
                (query.strip(), pattern, pattern, min(max(limit, 1), 100)),
            ).fetchall()
            return [dict(row) for row in rows]

    def archive_session(self, session_id: str, archived: bool, updated_at: str) -> None:
        with self.transaction() as connection:
            cursor = connection.execute("UPDATE sessions SET archived=?,updated_at=? WHERE session_id=?", (int(archived), updated_at, session_id))
            if cursor.rowcount != 1: raise KeyError(session_id)

    def touch_session(self, session_id: str, title: str, updated_at: str, model_id: str | None, model_revision: str | None, mode: str) -> None:
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE sessions SET title=?,updated_at=?,model_id=?,model_revision=?,conversation_mode=? WHERE session_id=?",
                (title, updated_at, model_id, model_revision, mode, session_id),
            )
            if cursor.rowcount != 1: raise KeyError(session_id)

    def rename_session(self, session_id: str, title: str, updated_at: str) -> None:
        if not title.strip() or len(title) > 200:
            raise ValueError("session title must contain 1-200 characters")
        with self.transaction() as connection:
            cursor = connection.execute("UPDATE sessions SET title=?,updated_at=? WHERE session_id=?", (title.strip(), updated_at, session_id))
            if cursor.rowcount != 1:
                raise KeyError(session_id)

    def save_message(self, message: dict) -> None:
        """Atomically store one complete message and all typed parts."""
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO messages(message_id,session_id,parent_id,role,created_at,active_version) VALUES(?,?,?,?,?,?)",
                (message["message_id"], message["session_id"], message.get("parent_id"),
                 message["role"], message["created_at"], message.get("active_version", 1)),
            )
            for ordinal, part in enumerate(message.get("parts", [])):
                connection.execute(
                    "INSERT INTO message_parts(message_id,ordinal,part_type,payload_json) VALUES(?,?,?,?)",
                    (message["message_id"], ordinal, part["type"], self.encode_part(part)),
                )

    def add_response_version(self, message_id: str, version: int, content: list[dict], metadata: dict) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO response_versions(message_id,version,content_json,model_id,model_revision,generation_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (message_id, version, json.dumps(content, ensure_ascii=False), metadata.get("model_id"),
                 metadata.get("model_revision"), json.dumps(metadata.get("generation", {})), metadata["created_at"]),
            )
            connection.execute("UPDATE messages SET active_version=? WHERE message_id=?", (version, message_id))

    def set_favorite(self, message_id: str, favorite: bool, created_at: str) -> None:
        with self.transaction() as connection:
            if favorite:
                connection.execute("INSERT OR REPLACE INTO favorites(message_id,created_at) VALUES(?,?)", (message_id, created_at))
            else:
                connection.execute("DELETE FROM favorites WHERE message_id=?", (message_id,))

    def set_feedback(self, message_id: str, rating: str | None, created_at: str) -> None:
        if rating not in {None, "good", "bad"}: raise ValueError("invalid feedback rating")
        with self.transaction() as connection:
            if rating is None:
                connection.execute("DELETE FROM feedback WHERE message_id=?", (message_id,))
            else:
                connection.execute("INSERT OR REPLACE INTO feedback(message_id,rating,created_at) VALUES(?,?,?)", (message_id, rating, created_at))

    def load_session(self, session_id: str) -> dict:
        with closing(self.connect()) as connection:
            session = connection.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if session is None: raise KeyError(session_id)
            messages = []
            for row in connection.execute(
                "SELECT * FROM messages WHERE session_id=? ORDER BY created_at,CASE role WHEN 'user' THEN 0 ELSE 1 END,message_id",
                (session_id,),
            ):
                item = dict(row)
                item["parts"] = [json.loads(part["payload_json"]) for part in connection.execute(
                    "SELECT payload_json FROM message_parts WHERE message_id=? ORDER BY ordinal", (row["message_id"],))]
                item["favorite"] = connection.execute("SELECT 1 FROM favorites WHERE message_id=?", (row["message_id"],)).fetchone() is not None
                feedback = connection.execute("SELECT rating FROM feedback WHERE message_id=?", (row["message_id"],)).fetchone()
                item["feedback"] = feedback["rating"] if feedback else None
                if row["role"] == "assistant":
                    item["versions"] = self.load_response_versions_with(connection, row["message_id"])
                    for version in item["versions"]:
                        version["voice_artifacts"] = [dict(artifact) for artifact in connection.execute(
                            "SELECT artifact_id,voice_model_id,voice_revision,voice_preset_id,created_at,duration,attempt FROM voice_artifacts WHERE message_id=? AND response_version=? ORDER BY attempt",
                            (row["message_id"], version["version"]))]
                messages.append(item)
            return {**dict(session), "messages": messages}

    @staticmethod
    def load_response_versions_with(connection: sqlite3.Connection, message_id: str) -> list[dict]:
        return [{**dict(row), "content": json.loads(row["content_json"]), "generation": json.loads(row["generation_json"] or "{}")}
                for row in connection.execute("SELECT * FROM response_versions WHERE message_id=? ORDER BY version", (message_id,))]

    def save_turn(self, session: dict, user_message: dict, assistant_message: dict) -> None:
        """Commit a completed user/assistant turn atomically after generation succeeds."""
        with self.transaction() as connection:
            connection.execute(
                "UPDATE sessions SET title=?,updated_at=?,model_id=?,model_revision=?,conversation_mode=? WHERE session_id=?",
                (session["title"], session["updated_at"], session.get("model_id"), session.get("model_revision"), session["conversation_mode"], session["session_id"]),
            )
            for message in (user_message, assistant_message):
                connection.execute(
                    "INSERT INTO messages(message_id,session_id,parent_id,role,created_at,active_version) VALUES(?,?,?,?,?,?)",
                    (message["message_id"], message["session_id"], message.get("parent_id"), message["role"], message["created_at"], 1),
                )
                for ordinal, part in enumerate(message["parts"]):
                    connection.execute(
                        "INSERT INTO message_parts(message_id,ordinal,part_type,payload_json) VALUES(?,?,?,?)",
                        (message["message_id"], ordinal, part["type"], self.encode_part(part)),
                    )
            connection.execute(
                "INSERT INTO response_versions(message_id,version,content_json,model_id,model_revision,generation_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (assistant_message["message_id"], 1, json.dumps(assistant_message["parts"], ensure_ascii=False),
                 session.get("model_id"), session.get("model_revision"), json.dumps(assistant_message.get("generation", {})), assistant_message["created_at"]),
            )

    def load_response_versions(self, message_id: str) -> list[dict]:
        with closing(self.connect()) as connection:
            return [{**dict(row), "content": json.loads(row["content_json"]), "generation": json.loads(row["generation_json"] or "{}")}
                    for row in connection.execute("SELECT * FROM response_versions WHERE message_id=? ORDER BY version", (message_id,))]

    def search(self, query: str, limit: int = 50) -> list[dict]:
        if not query.strip(): return []
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT DISTINCT s.* FROM sessions s LEFT JOIN messages m ON m.session_id=s.session_id "
                "LEFT JOIN message_parts p ON p.message_id=m.message_id "
                "WHERE s.title LIKE ? ESCAPE '\\' OR p.payload_json LIKE ? ESCAPE '\\' "
                "ORDER BY s.updated_at DESC LIMIT ?", (f"%{query}%", f"%{query}%", min(limit, 100)),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_assistant_version(self, message_id: str, version: int) -> dict:
        with closing(self.connect()) as connection:
            message = connection.execute(
                "SELECT m.role,m.session_id,s.character_id FROM messages m JOIN sessions s ON s.session_id=m.session_id WHERE m.message_id=?",
                (message_id,),
            ).fetchone()
            if not message or message["role"] != "assistant": raise KeyError(message_id)
            row = connection.execute("SELECT content_json FROM response_versions WHERE message_id=? AND version=?", (message_id, version)).fetchone()
            if not row: raise KeyError(f"{message_id}:{version}")
            parts = json.loads(row["content_json"])
            text = "\n".join(item.get("text", "") for item in parts if item.get("type") == "text")
            return {"message_id": message_id, "version": version, "text": text,
                    "session_id": message["session_id"], "character_id": message["character_id"]}

    def next_voice_attempt(self, message_id: str, version: int, preset_id: str) -> int:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT COALESCE(MAX(attempt),0)+1 FROM voice_artifacts WHERE message_id=? AND response_version=? AND voice_preset_id=?",
                                     (message_id, version, preset_id)).fetchone()
            return int(row[0])

    def save_voice_artifact(self, artifact: dict) -> None:
        with self.transaction() as connection:
            connection.execute("""INSERT INTO voice_artifacts(
                artifact_id,message_id,response_version,session_id,source_type,source_text,tts_text,character_id,
                voice_model_id,voice_revision,voice_style,voice_preset_id,parameters_json,created_at,latency,duration,
                file_size,favorite,relative_path,attempt,generation_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (artifact["artifact_id"], artifact.get("message_id"), artifact.get("response_version"), artifact.get("session_id"),
                 artifact.get("source_type", "message"), artifact.get("source_text", ""), artifact.get("tts_text", ""),
                 artifact.get("character_id", "shion"), artifact["voice_model_id"], artifact.get("voice_revision"),
                 artifact.get("voice_style", ""), artifact["voice_preset_id"], json.dumps(artifact.get("parameters", {})),
                 artifact["created_at"], artifact.get("latency_seconds", 0), artifact["duration"], artifact.get("file_size_bytes", 0),
                 int(bool(artifact.get("favorite"))), artifact["relative_path"], artifact["attempt"],
                 json.dumps(artifact.get("generation_metadata", {}))))

    def get_voice_artifact(self, artifact_id: str) -> dict:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM voice_artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
            if not row: raise KeyError(artifact_id)
            return self._decode_voice_artifact(row)

    def list_voice_artifacts(self, message_id: str, version: int) -> list[dict]:
        with closing(self.connect()) as connection:
            return [self._decode_voice_artifact(row) for row in connection.execute(
                "SELECT * FROM voice_artifacts WHERE message_id=? AND response_version=? ORDER BY attempt", (message_id, version))]

    def list_voice_artifact_index(self, character_id: str | None = None, limit: int = 200) -> list[dict]:
        with closing(self.connect()) as connection:
            if character_id:
                rows = connection.execute("SELECT * FROM voice_artifacts WHERE character_id=? ORDER BY created_at DESC LIMIT ?",
                                          (character_id, min(max(limit, 1), 500)))
            else:
                rows = connection.execute("SELECT * FROM voice_artifacts ORDER BY created_at DESC LIMIT ?", (min(max(limit, 1), 500),))
            return [self._decode_voice_artifact(row) for row in rows]

    @staticmethod
    def _decode_voice_artifact(row) -> dict:
        result = dict(row); result["generation_metadata"] = json.loads(result.pop("generation_json"))
        result["parameters"] = json.loads(result.pop("parameters_json")); result["favorite"] = bool(result["favorite"])
        result["latency_seconds"] = result.pop("latency"); result["file_size_bytes"] = result.pop("file_size")
        if not result["voice_style"]:
            result["voice_style"] = result["generation_metadata"].get("voice_style", "")
        if not result["latency_seconds"]:
            result["latency_seconds"] = result["generation_metadata"].get("latency_seconds", 0)
        return result

    def set_voice_artifact_favorite(self, artifact_id: str, favorite: bool) -> None:
        with self.transaction() as connection:
            cursor = connection.execute("UPDATE voice_artifacts SET favorite=? WHERE artifact_id=?", (int(favorite), artifact_id))
            if cursor.rowcount != 1: raise KeyError(artifact_id)

    def delete_voice_artifact(self, artifact_id: str) -> dict:
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM voice_artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
            if not row: raise KeyError(artifact_id)
            connection.execute("DELETE FROM voice_artifacts WHERE artifact_id=?", (artifact_id,))
            return self._decode_voice_artifact(row)

    def list_pronunciation_rules(self, character_id: str = "shion") -> list[dict]:
        with closing(self.connect()) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM pronunciation_rules WHERE character_id=? ORDER BY priority DESC,created_at,rule_id", (character_id,))]

    def create_pronunciation_rule(self, payload: dict) -> dict:
        original, replacement = str(payload.get("original_text", "")).strip(), str(payload.get("replacement", "")).strip()
        character_id = str(payload.get("character_id", "shion")); priority = int(payload.get("priority", 100))
        if not original or not replacement or len(original) > 200 or len(replacement) > 200: raise ValueError("invalid pronunciation rule")
        if not character_id.isascii() or not 1 <= len(character_id) <= 64 or not -1000 <= priority <= 1000: raise ValueError("invalid pronunciation scope")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds"); rule_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute("INSERT INTO pronunciation_rules(rule_id,original_text,replacement,enabled,character_id,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                               (rule_id, original, replacement, int(bool(payload.get("enabled", True))), character_id, priority, now, now))
            row = connection.execute("SELECT * FROM pronunciation_rules WHERE rule_id=?", (rule_id,)).fetchone()
        return dict(row)

    def update_pronunciation_rule(self, rule_id: str, changes: dict) -> dict:
        allowed = {"original_text", "replacement", "enabled", "character_id", "priority"}
        if not changes or any(key not in allowed for key in changes): raise ValueError("invalid pronunciation update")
        with closing(self.connect()) as connection:
            current = connection.execute("SELECT * FROM pronunciation_rules WHERE rule_id=?", (rule_id,)).fetchone()
        if not current: raise KeyError(rule_id)
        payload = {**dict(current), **changes}; original = str(payload["original_text"]).strip(); replacement = str(payload["replacement"]).strip()
        character_id = str(payload["character_id"]); priority = int(payload["priority"])
        if not original or not replacement or len(original) > 200 or len(replacement) > 200: raise ValueError("invalid pronunciation rule")
        if not character_id.isascii() or not 1 <= len(character_id) <= 64 or not -1000 <= priority <= 1000: raise ValueError("invalid pronunciation scope")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.transaction() as connection:
            connection.execute("UPDATE pronunciation_rules SET original_text=?,replacement=?,enabled=?,character_id=?,priority=?,updated_at=? WHERE rule_id=?",
                               (original, replacement, int(bool(payload["enabled"])), character_id, priority, now, rule_id))
            row = connection.execute("SELECT * FROM pronunciation_rules WHERE rule_id=?", (rule_id,)).fetchone()
        return dict(row)

    def delete_pronunciation_rule(self, rule_id: str) -> None:
        with self.transaction() as connection:
            cursor = connection.execute("DELETE FROM pronunciation_rules WHERE rule_id=?", (rule_id,))
            if cursor.rowcount != 1: raise KeyError(rule_id)

    def apply_pronunciation(self, text: str, character_id: str = "shion") -> str:
        value = text
        for rule in self.list_pronunciation_rules(character_id):
            if rule["enabled"]:
                value = value.replace(rule["original_text"], rule["replacement"])
        return value

    def integrity_status(self) -> dict:
        with closing(self.connect()) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()[0]
            counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("sessions", "messages", "voice_artifacts", "pronunciation_rules", "memories")}
            return {"state": "OK" if result == "ok" else "ERROR", "schema_version": SCHEMA_VERSION, "counts": counts}

    @staticmethod
    def encode_part(part: dict) -> str:
        return json.dumps(part, ensure_ascii=False, separators=(",", ":"))
