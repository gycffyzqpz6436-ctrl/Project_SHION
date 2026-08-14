from __future__ import annotations

import json
import re
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from app.storage.conversation_db import ConversationRepository


MEMORY_TYPES = frozenset({"preference", "profile", "project", "relationship", "decision",
                          "temporary", "character_specific", "system"})
MEMORY_SCOPES = frozenset({"global_owner", "character", "project", "conversation", "temporary"})
MEMORY_STATUSES = frozenset({"candidate", "active", "archived", "rejected", "expired"})
EXPLICIT_MEMORY_MARKERS = (
    "覚えて", "記憶して", "今後これを使って", "これで確定", "設定として扱って",
    "remember this", "please remember", "use this going forward",
)


class SensitiveMemoryError(ValueError):
    pass


class SensitiveMemoryFilter:
    _patterns = (
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
        re.compile(r"\b(?:password|passwd|api[_ -]?key|access[_ -]?token|auth(?:entication)?[_ -]?token|credential|secret)\s*[:=]\s*\S+", re.I),
        re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b"),
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    )

    @classmethod
    def reject(cls, content: str) -> None:
        if any(pattern.search(content) for pattern in cls._patterns):
            raise SensitiveMemoryError("Sensitive or credential-like content cannot be stored in Memory")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_content(content: str) -> str:
    return " ".join(content.replace("\u3000", " ").split()).strip().casefold()


def validate_expiration(value: object) -> str | None:
    if value is None or value == "": return None
    if not isinstance(value, str): raise ValueError("invalid Memory expiration")
    try: parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error: raise ValueError("invalid Memory expiration") from error
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def sanitize_metadata(value: object) -> dict:
    if not isinstance(value, dict): raise ValueError("invalid Memory metadata")
    allowed = {"project", "page", "tags", "extraction"}; result = {}
    for key, item in value.items():
        if key not in allowed: raise ValueError("invalid Memory metadata key")
        values = item if isinstance(item, list) else [item]
        if len(values) > 10 or any(not isinstance(entry, str) or len(entry) > 200 for entry in values):
            raise ValueError("invalid Memory metadata value")
        for entry in values: SensitiveMemoryFilter.reject(entry)
        result[key] = values if isinstance(item, list) else item
    return result


def _terms(value: str) -> set[str]:
    normalized = normalize_content(value)
    words = set(re.findall(r"[a-z0-9_]{2,}|[ぁ-んァ-ン一-龠]{2,}", normalized))
    japanese = "".join(re.findall(r"[ぁ-んァ-ン一-龠]", normalized))
    words.update(japanese[index:index + 2] for index in range(max(0, len(japanese) - 1)))
    return {item for item in words if item}


@dataclass(frozen=True)
class RetrievalContext:
    character_id: str = "shion"
    conversation_id: str | None = None
    project: str | None = None
    page: str | None = None


class MemoryRetriever:
    """Deterministic retrieval boundary; replaceable by a future vector adapter."""

    def __init__(self, repository: ConversationRepository, max_items: int = 6, max_characters: int = 1600) -> None:
        self.repository = repository
        self.max_items = max_items
        self.max_characters = max_characters

    def retrieve(self, query: str, context: RetrievalContext) -> list[dict]:
        now = utc_now(); query_terms = _terms(query); scored = []
        with self.repository.transaction() as connection:
            connection.execute("UPDATE memories SET status='expired',updated_at=? WHERE status='active' AND expires_at IS NOT NULL AND expires_at<=?", (now, now))
            rows = connection.execute(
                "SELECT * FROM memories WHERE status='active' AND owner_approved=1 AND superseded_by IS NULL "
                "AND (expires_at IS NULL OR expires_at>?) AND (scope='global_owner' OR character_id=?)",
                (now, context.character_id),
            ).fetchall()
            for row in rows:
                item = dict(row); metadata = json.loads(item.pop("metadata_json") or "{}")
                if item["scope"] == "conversation" and item["source_conversation_id"] != context.conversation_id: continue
                if item["scope"] == "project" and metadata.get("project") and metadata.get("project") not in {context.project, context.page}: continue
                overlap = len(query_terms & _terms(item["normalized_content"]))
                if not item["pinned"] and overlap == 0: continue
                score = overlap * 10 + item["importance"] * 2 + (30 if item["pinned"] else 0)
                scored.append((score, item["updated_at"], {**item, "metadata": metadata}))
            selected, used = [], 0
            for _, _, item in sorted(scored, key=lambda entry: (entry[0], entry[1]), reverse=True):
                size = len(item["content"])
                if selected and used + size > self.max_characters: continue
                if size > self.max_characters: item["content"] = item["content"][:self.max_characters]
                selected.append(item); used += min(size, self.max_characters)
                if len(selected) >= self.max_items: break
            if selected:
                ids = [item["id"] for item in selected]
                connection.executemany("UPDATE memories SET retrieval_count=retrieval_count+1,last_used_at=? WHERE id=?", ((now, item) for item in ids))
            return selected


class MemoryContextBuilder:
    labels = {"preference": "Preference", "profile": "Owner Profile", "project": "Project",
              "relationship": "Character Relationship", "decision": "Project Decision",
              "temporary": "Temporary", "character_specific": "Character", "system": "System"}

    @classmethod
    def build(cls, memories: Iterable[dict], max_characters: int = 1800) -> str:
        lines = ["[Relevant Long-Term Memory]"]
        for memory in memories:
            line = f"- {cls.labels.get(memory['type'], memory['type'])}: {memory['content']}"
            if len("\n".join([*lines, line])) > max_characters: break
            lines.append(line)
        return "" if len(lines) == 1 else "\n".join(lines)


class MemoryService:
    available = True

    def __init__(self, repository: ConversationRepository) -> None:
        self.repository = repository
        self.retriever = MemoryRetriever(repository)
        self.last_error: str | None = None

    @staticmethod
    def _decode(row) -> dict:
        item = dict(row); item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        item["owner_approved"] = bool(item["owner_approved"]); item["pinned"] = bool(item["pinned"])
        return item

    def create(self, payload: dict, *, source_author: str = "owner", candidate: bool = False) -> dict:
        content = str(payload.get("content", "")).strip()
        if not content or len(content) > 2000: raise ValueError("Memory content must contain 1-2000 characters")
        SensitiveMemoryFilter.reject(content)
        memory_type = payload.get("type", "preference"); scope = payload.get("scope", "global_owner")
        character_id = payload.get("character_id", "shion")
        if memory_type not in MEMORY_TYPES or scope not in MEMORY_SCOPES: raise ValueError("invalid Memory type or scope")
        if not isinstance(character_id, str) or not character_id.isascii() or not character_id: raise ValueError("invalid character binding")
        if source_author not in {"owner", "assistant", "external", "system"}: raise ValueError("invalid Memory provenance")
        if source_author != "owner" and not candidate: raise ValueError("non-Owner content cannot create active Memory")
        status = "candidate" if candidate else "active"; approved = not candidate and source_author == "owner"
        importance = int(payload.get("importance", 3)); confidence = float(payload.get("confidence", 1 if approved else .9))
        if not 1 <= importance <= 5 or not 0 <= confidence <= 1: raise ValueError("invalid Memory ranking")
        expiration = validate_expiration(payload.get("expires_at"))
        now = utc_now(); memory_id = str(uuid.uuid4()); supersedes = payload.get("supersedes")
        metadata = sanitize_metadata(payload.get("metadata", {}))
        with self.repository.transaction() as connection:
            duplicate = connection.execute("SELECT id FROM memories WHERE normalized_content=? AND type=? AND character_id=? AND scope=? AND status NOT IN ('rejected','expired')", (normalize_content(content), memory_type, character_id, scope)).fetchone()
            if duplicate: raise ValueError("duplicate Memory record")
            if supersedes:
                previous = connection.execute("SELECT id FROM memories WHERE id=?", (supersedes,)).fetchone()
                if not previous: raise KeyError(supersedes)
            connection.execute(
                "INSERT INTO memories(id,type,character_id,scope,content,normalized_content,source_conversation_id,source_message_id,source_author,created_at,updated_at,expires_at,status,confidence,importance,owner_approved,pinned,metadata_json,supersedes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (memory_id, memory_type, character_id, scope, content, normalize_content(content), payload.get("source_conversation_id"),
                 payload.get("source_message_id"), source_author, now, now, expiration, status,
                 confidence, importance, int(approved),
                 int(bool(payload.get("pinned"))), json.dumps(metadata, ensure_ascii=False), supersedes),
            )
            if supersedes and approved:
                connection.execute("UPDATE memories SET superseded_by=?,updated_at=? WHERE id=?", (memory_id, now, supersedes))
            row = connection.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        return self._decode(row)

    def list(self, status: str | None = None, character_id: str | None = None) -> list[dict]:
        self.expire_due(); clauses, values = [], []
        if status:
            if status not in MEMORY_STATUSES: raise ValueError("invalid Memory status")
            clauses.append("status=?"); values.append(status)
        if character_id: clauses.append("character_id=?"); values.append(character_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self.repository.connect()) as connection:
            return [self._decode(row) for row in connection.execute(f"SELECT * FROM memories{where} ORDER BY pinned DESC,importance DESC,updated_at DESC LIMIT 200", values)]

    def get(self, memory_id: str) -> dict:
        with closing(self.repository.connect()) as connection:
            row = connection.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
            if not row: raise KeyError(memory_id)
            item = self._decode(row)
            item["versions"] = [dict(version) for version in connection.execute("SELECT * FROM memory_versions WHERE memory_id=? ORDER BY version DESC", (memory_id,))]
            return item

    def update(self, memory_id: str, changes: dict) -> dict:
        allowed = {"content", "type", "character_id", "scope", "importance", "pinned", "expires_at", "metadata"}
        if not changes or any(key not in allowed for key in changes): raise ValueError("invalid Memory update")
        current = self.get(memory_id); content = str(changes.get("content", current["content"])).strip()
        SensitiveMemoryFilter.reject(content)
        memory_type = changes.get("type", current["type"]); scope = changes.get("scope", current["scope"])
        if memory_type not in MEMORY_TYPES or scope not in MEMORY_SCOPES: raise ValueError("invalid Memory type or scope")
        character_id = changes.get("character_id", current["character_id"])
        if not isinstance(character_id, str) or not character_id.isascii(): raise ValueError("invalid character binding")
        importance = int(changes.get("importance", current["importance"])); expiration = validate_expiration(changes.get("expires_at", current["expires_at"]))
        if not 1 <= importance <= 5: raise ValueError("invalid Memory importance")
        metadata = sanitize_metadata(changes.get("metadata", current["metadata"]))
        now = utc_now(); next_version = current["version"] + 1
        with self.repository.transaction() as connection:
            duplicate = connection.execute("SELECT id FROM memories WHERE id<>? AND normalized_content=? AND type=? AND character_id=? AND scope=? AND status NOT IN ('rejected','expired')", (memory_id, normalize_content(content), memory_type, character_id, scope)).fetchone()
            if duplicate: raise ValueError("duplicate Memory record")
            connection.execute("INSERT INTO memory_versions(memory_id,version,content,normalized_content,type,character_id,scope,status,importance,pinned,metadata_json,changed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (memory_id, current["version"], current["content"], current["normalized_content"], current["type"], current["character_id"], current["scope"], current["status"], current["importance"], int(current["pinned"]), json.dumps(current["metadata"], ensure_ascii=False), now))
            connection.execute("UPDATE memories SET content=?,normalized_content=?,type=?,character_id=?,scope=?,importance=?,pinned=?,expires_at=?,metadata_json=?,updated_at=?,version=? WHERE id=?",
                (content, normalize_content(content), memory_type, character_id, scope, importance, int(bool(changes.get("pinned", current["pinned"]))), expiration, json.dumps(metadata, ensure_ascii=False), now, next_version, memory_id))
        return self.get(memory_id)

    def transition(self, memory_id: str, action: str) -> dict:
        transitions = {"approve": ("active", 1), "archive": ("archived", None), "restore": ("active", None), "reject": ("rejected", 0)}
        if action not in transitions: raise ValueError("invalid Memory transition")
        status, approved = transitions[action]; now = utc_now()
        with self.repository.transaction() as connection:
            row = connection.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
            if not row: raise KeyError(memory_id)
            if action == "approve" and row["source_author"] != "owner": raise ValueError("Only Owner-authored candidates may be approved")
            clear_expiration = action == "restore" and row["expires_at"] and row["expires_at"] <= now
            connection.execute("UPDATE memories SET status=?,owner_approved=COALESCE(?,owner_approved),expires_at=CASE WHEN ? THEN NULL ELSE expires_at END,updated_at=? WHERE id=?",
                               (status, approved, int(bool(clear_expiration)), now, memory_id))
            if action == "approve" and row["supersedes"]:
                connection.execute("UPDATE memories SET superseded_by=?,updated_at=? WHERE id=?", (memory_id, now, row["supersedes"]))
        return self.get(memory_id)

    def delete(self, memory_id: str) -> None:
        with self.repository.transaction() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            if cursor.rowcount != 1: raise KeyError(memory_id)

    def expire_due(self) -> int:
        now = utc_now()
        with self.repository.transaction() as connection:
            cursor = connection.execute("UPDATE memories SET status='expired',updated_at=? WHERE status='active' AND expires_at IS NOT NULL AND expires_at<=?", (now, now))
            return cursor.rowcount

    def extract_candidate(self, message: str, conversation_id: str, message_id: str,
                          character_id: str = "shion") -> dict | None:
        lowered = message.casefold(); marker = next((item for item in EXPLICIT_MEMORY_MARKERS if item in lowered), None)
        if not marker: return None
        content = re.sub(re.escape(marker), "", message, count=1, flags=re.I).strip(" ：:、。")
        if not content: return None
        SensitiveMemoryFilter.reject(content)
        memory_type = self.classify(content)
        scope = "character" if memory_type in {"relationship", "character_specific"} else "project" if memory_type in {"project", "decision"} else "global_owner"
        return self.create({"content": content, "type": memory_type, "scope": scope, "character_id": character_id,
                            "source_conversation_id": conversation_id, "source_message_id": message_id,
                            "confidence": .95, "metadata": {"extraction": "explicit_owner_request"}}, source_author="owner", candidate=True)

    @staticmethod
    def classify(content: str) -> str:
        lowered = content.casefold()
        if any(word in lowered for word in ("project", "プロジェクト", "shion")): return "project"
        if any(word in lowered for word in ("決定", "確定", "decision")): return "decision"
        if any(word in lowered for word in ("呼んで", "関係", "relationship")): return "relationship"
        if any(word in lowered for word in ("期限", "まで", "temporary")): return "temporary"
        if any(word in lowered for word in ("好き", "嫌い", "prefer", "好み")): return "preference"
        return "profile"

    def relevant_context(self, query: str, *, character_id: str, conversation_id: str | None,
                         project: str | None = None, page: str | None = None) -> tuple[str, list[dict]]:
        selected = self.retriever.retrieve(query, RetrievalContext(character_id, conversation_id, project, page))
        return MemoryContextBuilder.build(selected), selected
