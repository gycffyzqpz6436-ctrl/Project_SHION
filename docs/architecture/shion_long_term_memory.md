# SHION Long-Term Memory — Phase F

## Purpose and boundary

Long-Term Memory is an Owner-controlled, persistent context layer. It is not Conversation History: History preserves what was said, while Memory stores a small set of facts or preferences that the Owner can inspect, approve, edit, archive, restore, reject, pin, or permanently delete. Automatic permanent promotion is OFF.

The implementation uses the existing local Conversation SQLite database and schema version 4. It does not add a vector database, cloud sync, external document ingestion, or a browser copy of the full database. Floating SHION reaches Memory only through the normal backend retrieval boundary.

## Lifecycle and provenance

Records use `candidate`, `active`, `archived`, `rejected`, and `expired` states. Direct Owner UI creation produces an approved active record. Explicit phrases such as 「覚えて」 or “remember this” may create a high-confidence Owner candidate, but never an active record. Ordinary chat does not extract or promote records. Assistant, external, and tool content cannot create approved Owner facts.

Every record retains type, character, scope, normalized content, source conversation/message when applicable, timestamps, expiration, confidence, importance, approval, pin, retrieval count, metadata, version history, and supersession links. Edits preserve the preceding value in `memory_versions`; superseded records are excluded from retrieval. Hard Delete requires the Owner to type `DELETE` and removes that record and its version history.

## Retrieval and prompt isolation

`MemoryRetriever` is a replaceable deterministic adapter. It filters to active, Owner-approved, unexpired, nonsuperseded records; enforces character and conversation/project scope; then ranks text overlap, pinned state, importance, and recency. Retrieval is capped by item and character budgets. The result is rendered as a separate `[Relevant Long-Term Memory]` prompt layer, never inserted into stored conversation history.

Memory lookup or persistence failure is non-fatal to Chat. The response proceeds without Memory and exposes a generic subsystem error without logging private content.

## Privacy and local API

Credential-like assignments, API/access tokens, private keys, and payment-card-like values are rejected before persistence. Metadata has a small allowlist and the same sensitive-value filter. Browser mutations pass the existing localhost/Tailscale Host and Origin boundary and a valid session identifier. Public API surfaces are:

- `GET /api/memory`, `/api/memory/candidates`, `/api/memory/{id}`
- `POST /api/memory`, plus approve/archive/restore/reject transitions
- `PATCH /api/memory/{id}`
- `DELETE /api/memory/{id}` with `confirm: "DELETE"`

## Migration, backup, and recovery

Schema migration is additive from supported Conversation schema versions 1–3 to 4 and creates the default `automatic_promotion=false` setting. Before manual database repair or rollback, stop SHION and copy `%SHION_DATA_ROOT%\data\conversations\shion_chat.db` together with its `-wal` and `-shm` files when present. Restore only while SHION is stopped. Never commit these runtime files.

## Deferred Owner Gates

Automatic promotion, vector/embedding retrieval, broader sensitive-memory categories, cross-character sharing, Desktop Companion Memory access, cloud synchronization, and external knowledge ingestion remain separate Owner Gates.
