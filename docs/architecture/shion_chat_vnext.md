# SHION Chat vNext architecture

## Scope and current state

SHION Chat remains bound to `127.0.0.1:8765`. Remote access is a Tailscale Serve boundary and is not changed by vNext. The Tailscale HTTPS certificate issue is an external blocker and is deliberately outside this work.

The current runtime has an in-memory `SessionStore`, one allowlisted conversation-model runtime, a conversation-only `ShionOrchestrator`, default-disabled tools and long-term memory, and a separate localhost Style-Bert-VITS2 process. Existing histories remain compatible `role/content` pairs while typed message contracts are introduced beside them.

## Target boundaries

```text
Web UI
  -> ShionRuntime
     -> ShionOrchestrator
        -> Conversation Model
        -> Session Service (SQLite canonical history + in-memory model context)
        -> Export Service (explicit browser download only)
        -> Voice Controller boundary (separate process)
        -> future Image / Vision / Memory / Knowledge adapters (disabled)
```

The conversation model never receives filesystem paths and cannot directly invoke Voice, image, Vision, memory, shell, or network capabilities.

## Message and session migration

`app/core/message.py` defines stable message identity, parent identity, typed parts, model/revision, generation metadata, feedback and favorite fields. Supported part types are `text`, `image`, `audio`, `attachment`, and `tool_result`.

Migration is additive: the model context continues to consume the existing `role/content` projection. API responses expose identity and generation metadata. No disk schema or automatic migration is activated. A future persistent store must explicitly define storage root, encryption, retention, deletion, indexes, migrations and corruption recovery before Owner approval.

Regeneration replaces the active response in model context while the browser may retain the earlier response as a visible version. Full branch persistence and history search remain gated.

## Feature dependency phases

1. Message UX: copy, regenerate, failure retry, ephemeral favorite/feedback, details, latest jump, session draft, connection states, Japanese IME and mobile composer.
2. Voice: approved-preset discovery, read-aloud, retry and auto-play, with failure isolation. Requires a reviewed IPC/API contract and GPU coexistence measurements.
3. Session architecture: typed IDs, parents, versions and branch foundation. Persistence remains OFF pending Owner Gate.
4. Export: explicit Markdown/TXT/JSONL and Dataset Candidate downloads. Candidate export must never write Golden, Database or training data automatically.
5. Typed multimodal rendering: parts and artifact references only; no image/Vision/STT backend is enabled.
6. PWA/mobile companion: manifest, caching and audio policy only after the external HTTPS blocker is resolved.

## Security and privacy

- Bind remains loopback-only; Funnel, public exposure, LAN direct access and router forwarding remain denied.
- Host, Origin, CSRF-relevant request checks and CSP remain enforced.
- Models remain server allowlisted; arbitrary model and filesystem paths remain denied.
- Chat history, response versions, favorites and feedback persist locally in SQLite. Drafts use `sessionStorage` only.
- No feedback telemetry exists. Favorite and feedback never promote data to Golden, rejected data, or training data.
- Attachments and microphone controls are disabled placeholders. No browser permission is requested.
- Generated media, private conversations, models, caches and runtime artifacts must remain outside Git.

## Resource impact

Message UX and typed contracts have negligible GPU impact. Conversation model switching retains the existing unload/GC/CUDA-cache boundary. Voice integration is not enabled until Gemma/TTS simultaneous VRAM, latency, load time and OOM behavior are measured on the RTX 5070 12 GB.

## Test plan

- Unit tests for message contracts, response metadata, regenerate behavior and access policy.
- Browser tests for send, stop, retry, regenerate, feedback, favorite, draft, IME, latest jump, mode/model switching and disabled future slots.
- Localhost PASS; approved Tailscale proxy policy PASS; LAN/forged Host/forged identity FAIL.
- Python compilation, JavaScript syntax and `git diff --check`.

## Owner gates

Owner approval is required before persistent conversation storage, long-term memory, Stable Diffusion, Vision, STT/microphone permission, model downloads, training, Dataset writes, Canonical semantic changes, PWA caching, or any public network exposure.

## Future Desktop SHION Companion extension point

The Desktop SHION Companion is a future Windows-resident client, not part of
Phase 1 and not another form of the Web UI Floating Assistant. The Floating
Assistant remains a component inside the SHION Dashboard browser document. The
Desktop Companion will have its own process, window lifecycle, update boundary,
permission state and failure isolation, and may remain available while another
Windows application is active.

Both clients may consume the same local, typed application contracts for
Conversation, Voice and Character state. They must not share DOM state, browser
storage, window-management code, capture permissions or presentation lifecycle.
The future boundary is:

```text
SHION Dashboard
  -> Web Floating Assistant (browser presentation)
  -> Local SHION application API

Desktop SHION Companion (future Windows client)
  -> Companion permission broker (default deny)
  -> Companion renderer interface (2D first; 3D replaceable)
  -> Local SHION application API

Local SHION application API
  -> Conversation / Voice / Character backends
```

The initial product shape may be an always-on-top compact official 2D Avatar
window with Mini Chat, Nene Voice, notifications and an explicit command to open
the SHION Dashboard. Always-on-top, launch-at-login, notifications, microphone
use and Dashboard launch are client capabilities, not authorities granted to the
Conversation Model. The renderer consumes bounded Character presentation state;
it cannot invoke tools or inspect the desktop. A future 3D renderer must be
selectable behind the same renderer contract without changing Conversation,
Voice or Character backend contracts.

Desktop context access is split into separately named Owner permissions, each
default OFF: active application identity, window title, screen capture and
selected text. Additional sources require additional permissions rather than
being grouped under a general desktop-access switch. The permission broker must
enforce purpose-bound, explicit acquisition and a visible active-capture state.
It must support immediate revocation and must not continuously collect, retain or
forward context merely because the Companion is running. Secret fields,
password/authentication surfaces, private/incognito windows and other protected
content require deny/redaction rules; no source may be treated as safe solely
because Windows exposes an API for it.

Before implementation, Owner review must approve the IPC/authentication model,
permission UX and persistence, protected-content policy, capture indicators,
retention/logging rules, renderer package trust, notification behavior,
auto-start behavior and process/update strategy. Phase 1 creates no Companion
executable, background process, startup entry, global hook, accessibility/UI
Automation reader, clipboard listener, capture session or new Windows permission.

## Workspace Phase A-C official Static 2D integration

Status: **COMPLETE**. The previous `OFFICIAL 2D ASSET REQUIRED` blocker was
resolved by Owner approval and registration of `official_static_2d_v1` on
2026-08-14.

Workspace Phase A-C resolves Character presentation through a generic Character
profile and versioned asset manifest. SHION is registered with
`character_id=shion`, `renderer.type=static_2d`, and
`asset_set=official_static_2d_v1`; the set is Owner-approved and official.
Avatar, Panel and Master assets have distinct roles and SHA-256 metadata. UI code
loads one profile/manifest boundary rather than hard-coding SHION image paths at
each use site.

Presentation states (`idle`, `thinking`, `generating`, `speaking`, `happy`,
`playful`, `concerned`) currently resolve to the same Panel asset. This is an
extension point for future approved variants, not authorization to generate
expressions. Missing or invalid assets fall back to the existing local SHION mark
and display an unavailable state. The same profile schema can register NONO or
美月 later without changing the renderer contract.

## Phase 1.5 runtime lifecycle

On Windows, the `training/.venv/Scripts/python.exe` process is a small venv launcher whose child is the system Python interpreter running the same command. This parent/child pair is one server, not two model instances. The server disables socket address reuse and binds `127.0.0.1:8765` before starting model load, so a second instance fails before allocating model RAM. Graceful shutdown closes the HTTP listener, releases the model runtime and clears all in-memory sessions.

Process memory must distinguish Working Set from Private Bytes. Private Bytes includes committed virtual/pagefile-backed allocations and is not equivalent to resident physical RAM. Resource reviews record both, plus system available RAM, VRAM and post-generation recovery. Long repeated-generation benchmarks remain Owner-run when they may become a lengthy GPU workload.

## Phase 1.5 session lifecycle

`New Chat` creates a new stable session identity and switches `active_session_id`; it does not reset or delete the prior session. During one browser-tab session, `sessionStorage` contains multiple isolated sessions with messages, versions, favorite/feedback marks, mode and draft. The sidebar switches between them. Reload restores them; closing the browser session may discard them. `localStorage` is not used.

The three storage levels remain explicit:

1. current DOM/message state;
2. ephemeral multi-session state in `sessionStorage`;
3. SQLite persistent history as the canonical source after Phase 1.6 Owner approval.

## Unified runtime storage

`StoragePaths` resolves an explicit path, then `SHION_DATA_ROOT`, then the safe default `D:\AI\Project_SHION`. Runtime-derived paths are centralized:

- conversation DB: `data/conversations/shion_chat.db`
- Voice/image/attachment/export artifacts: `artifacts/<type>`
- Hugging Face cache: `cache/huggingface`
- temporary data and logs: `temp`, `logs`

The repository remains on C: and contains only source, tests, documentation and lightweight configuration. Voice data was moved into the unified D: root after explicit Phase 1.6 Owner approval; the empty legacy root remains pending separate deletion approval.

The Owner-gated migration stopped Voice processes, inventoried source and destination, validated the registry, checked collisions/free space, used same-volume moves, verified counts and bytes, rewrote paths and ran offline validation. The source was about 10 GiB and the operation created no long-lived duplicate.

## Conversation SQLite foundation

SQLite is sufficient for this single-owner local application. Schema version 1 defines `sessions`, `messages`, `message_parts`, `response_versions`, `favorites` and `feedback`, with optional future artifact/branch/export tables deferred. Connections enable foreign keys, WAL, a five-second busy timeout and explicit transactions. Phase 1.6 production startup enables the repository; unit tests retain an explicit disabled mode.

The active location is `%SHION_DATA_ROOT%\data\conversations\shion_chat.db`. It is never served as a static file. Conversation History answers what was said in a session; Long-Term Memory remains a separate disabled subsystem and receives no automatic promotion.

## Phase 1.6 persistence activation

Owner approval activates schema-versioned SQLite history at `%SHION_DATA_ROOT%\data\conversations\shion_chat.db`. The database is the canonical source for sessions, messages, response versions, favorites and feedback. A completed user/assistant turn is committed atomically. Sidebar History, Search and Rename read and write this store; server restart and browser reload rehydrate it. `sessionStorage` now contains only the active session ID and unsent drafts, and `localStorage` remains unused.

Regeneration adds a response version beneath the stable assistant-message identity. Selecting a version changes the canonical response used by model context while retaining earlier versions. Long-Term Memory remains a distinct disabled subsystem and receives no automatic promotion from History.

Schema migration failures are surfaced as `History UNAVAILABLE` through `/api/status`; chat generation remains usable through an explicit ephemeral fallback. Connections enforce foreign keys, WAL, a five-second busy timeout and explicit transactions.

Retention is OFF: history remains until an Owner action. Archive/soft-delete is the default removal policy. Hard delete and artifact cascade require separate approval. SQLite's online backup API is the approved backup foundation, but this phase schedules no background copy and never silently exports private history. DB/WAL/SHM, exports and private artifacts remain Gitignored.

## Phase 1.6 Voice migration result

After Owner approval, Voice models, runtime, venv, registry, caches, logs, temp and artifacts were moved on the same D: volume into corresponding `D:\AI\Project_SHION` subtrees. The operation first confirmed no active Voice listener, inventoried both roots, validated the registry, checked collisions and free space, and then verified file counts and byte totals. Offline diagnostics and a real JVNV F1 44.1 kHz WAV generation passed after relocation. No large duplicate remains. The empty legacy `D:\AI\Project_SHION_Voice` root is deliberately retained until separate deletion approval.

## Phase 1.6 runtime benchmark

Five sequential Japanese generations ran in one persistent Neutral session on Gemma 4 12B Heretic JA v2. Values are MiB; triples are before / best observable peak / after.

| Generation | Latency | Python Working Set | Python Private Bytes | NVIDIA VRAM | Minimum free RAM | Peak system commit |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.764 s | 1499.0 / 1499.3 / 1499.1 | 11359.2 / 11359.4 / 11359.2 | 9057 / 9215 / 9215 | 18626 | 30152.6 |
| 2 | 2.328 s | 1499.1 / 1499.3 / 1499.2 | 11359.2 / 11359.4 / 11359.2 | 9183 / 9221 / 9217 | 18624 | 30189.0 |
| 3 | 2.932 s | 1499.2 / 1499.3 / 1499.2 | 11359.2 / 11359.4 / 11359.3 | 9181 / 9217 / 9204 | 18603 | 30192.2 |
| 4 | 4.663 s | 1499.2 / 1499.7 / 1499.6 | 11359.3 / 11359.7 / 11359.6 | 9139 / 9215 / 9041 | 18596 | 30215.9 |
| 5 | 4.051 s | 1499.6 / 1499.8 / 1499.7 | 11359.6 / 11359.7 / 11359.6 | 9144 / 9221 / 9144 | 18697 | 30090.6 |

RTX 5070 total VRAM was 12,227 MiB. Post-generation Working Set changed by only 0.6 MiB and Private Bytes by 0.4 MiB across the corrected five-run sample; VRAM returned near its generation baseline. No monotonic physical-RAM or VRAM leak was detected. Windows exposed system commit but no supported per-process Memory Compression counter in this environment, so compression-specific attribution is inconclusive rather than inferred from Task Manager percentage.

## Workspace Phase D-E review boundary

Phase D introduces a read-only `CharacterRegistry` whose canonical SHION record is
the repository profile and Owner-approved asset manifest. Conversation schema v3
adds a stable `character_id`; existing sessions migrate additively to `shion` and
generation never rewrites that binding. Multi-character behavior, relationship
state and renderer upgrades remain unavailable.

Phase E adds Home, Characters, Voice Lab, System and SHION Room presentation
surfaces without creating the deferred backends. Dashboard data is assembled from
existing conversation, runtime, Character and Voice adapters. System telemetry is
minimal, manually refreshed and excludes credentials and private filesystem paths.
Voice Lab uses only the approved `SHION Default` Nene V3/Bright preset, bounded
temporary parameters and opaque audio artifact IDs; experiments do not mutate the
saved preset or conversation records.

The in-Web-UI Floating Assistant is a compact view over the same Conversation
backend. It accepts only an explicit bounded Workspace-context allowlist. It is not
the future Windows Desktop Companion: no window-title, screen, selection-text or
other application access exists, and each such capability remains a separate
default-OFF Owner permission extension point.

## Phase D-E Owner UX revision

The daily-use Chat surface owns a persistent `autoFollow` presentation state.
Sending, regenerating or explicitly choosing Jump to Latest enables bottom lock;
an Owner scroll away from the latest content disables it. Typewriter updates and
late Voice controls follow only while this state remains enabled. Mobile Enter is
a newline and the Send button submits; desktop keeps IME-safe Enter submission.

Home is the assistant landing surface and contains no resource telemetry. System
owns manually refreshed DB, process, RAM, GPU and storage status. The right panel
is a renderer-neutral Character Presence surface rather than another System page.
Chat backgrounds are a CSS/asset boundary with contrast-preserving defaults; no
decorative background pack is bundled in this revision.

Memory is an explicitly disabled Owner Memory schema/UI foundation, separate from
the Character Bible and Conversation History. Settings stores only working
presentation preferences in browser-session storage. It cannot enable Memory,
change the approved Character or claim unavailable backends.

Voice Lab exposes only adapter-verified allowlisted parameters as bounded sliders.
Display text and TTS transformation remain separate. Direct accent/phoneme control
is labelled unsupported until the isolated Style-Bert-VITS2 adapter proves a safe
contract; pronunciation dictionary persistence remains an Owner Gate.

### Phase D-E GPU Resource Safety Owner Review

`GpuResourceGate` is the shared GPU ownership boundary for Conversation and every
Voice entry point: Read Aloud, Retry Voice, Auto Play and Voice Lab. LLM generation
acquires ownership before entering `Generating` and releases it from `finally`, so
failure and Owner cancellation cannot strand the gate. Voice requests submitted
while LLM generation owns the GPU remain in a bounded FIFO queue with deduplication
by message ID, response version and preset/model selection. The queue has an
explicit limit and timeout. Session changes, response-version changes and Owner
cancel remove matching waiting requests. The UI presents `WAITING_FOR_GPU` with
"会話生成完了後に音声を生成します" rather than claiming that synthesis started.

After LLM release the gate requires runtime `Ready`, waits a short settle interval,
then permits one Voice request. The existing Voice exclusive lock remains in place.
VRAM free is exposed only as telemetry; it is not an admission predicate. Gemma and
Voice resident/unload policies are unchanged.

RTX 5070 (12,227 MiB) review measurements observed Gemma Heretic generation at
11,880 MiB used / 64 MiB free. A later Voice E2E observed 11,240 / 704 MiB before,
11,804 / 140 MiB at sampled peak, and 11,658 / 286 MiB at the stable 30-second
post-generation point. The Voice artifact used SHION Default, Nene V3 and Bright;
latency was 10.896 seconds for 2.566 seconds of audio. However, final runtime
inspection for that Voice E2E reported `ministral3_official`. Therefore this is not
recorded as a strict "Heretic idle + Voice" measurement. That measurement remains
separate from the later Owner-verified Heretic validation below.

The subsequent Owner-verified contention run used runtime alias
`gemma4_12b_heretic_ja_v2_manual`. Voice was submitted only after Heretic entered
`Generating`. Observed ordering was: Voice `WAITING_FOR_GPU` with queue depth one,
LLM HTTP completion, runtime `Ready`, gate `GENERATING` after the settle boundary,
Voice listener availability, Voice completion, then gate `READY` with an empty
queue. The LLM took 37.172 seconds. First-load Voice used SHION Default / Nene V3 /
Bright and completed successfully without overlap or OOM.

Strict warm Heretic idle + Voice measurements on RTX 5070 12,227 MiB:

| Point | Used VRAM | Free VRAM |
|---|---:|---:|
| Heretic + resident Voice idle baseline | 10,416-10,418 MiB | 1,526-1,528 MiB |
| Voice generation sampled peak | 10,458 MiB | 1,486 MiB |
| 30-second post-settle | 10,420-10,421 MiB | 1,523-1,524 MiB |

The warm Voice request completed in 0.703 seconds wall / 0.661 seconds inference
for 3.019 seconds of audio. Post-validation gate state was `READY`, queue depth was
zero and `llm_active` was false. The earlier first-load contention run peaked at
10,402 MiB and settled at 10,397-10,402 MiB before the separated warm sample.

## Phase 2 Voice integration

SHION Chat never imports Style-Bert-VITS2. `VoiceServiceClient` is an application-side Controller/Backend Adapter that starts and communicates with the isolated loopback Voice service in its dedicated D: venv. The conversation model receives no Voice capability and no filesystem path. Text generation completes and persists before optional TTS begins; a Voice exception only marks Voice `ERROR` and never removes or regenerates the response.

Read Aloud accepts only a persisted assistant `message_id` plus response version. The server retrieves that version from SQLite, applies deterministic Markdown/URL normalization with a 500-character ceiling, and sends it to the isolated backend. Arbitrary public TTS text and arbitrary paths are not accepted. TTS requests are serialized by an exclusive Voice lock.

Schema v2 adds `voice_artifacts`, storing stable artifact ID, message/version identity, fixed Voice model revision, preset ID, attempt, timestamps, duration, relative path and metrics. WAV bytes remain under `D:\AI\Project_SHION\artifacts\voice`. The browser resolves only a registered UUID; the resolver confines the relative path to that root. Responses use `audio/wav`, `nosniff`, private/no-store caching and byte ranges for Safari. Automatic deletion remains OFF.

Normal mode lists only Owner-approved presets. The Owner-approved `SHION Default` preset resolves independently of browser storage to Voice Model `nene_v3_candidate` (Nene V3) with fixed `Bright` style. It is selected after a new browser session, reload and server restart without enabling Developer Voice. The underlying Model Registry entry remains separate and retains Neutral/Bright/Soft; Nene Whisper, JVNV and other Ready models remain explicit Developer Voice choices. Auto Play is OFF by default and stored only as tab-local UI preference; when enabled it uses the same selected approved preset. Browser autoplay rejection is reported as a tap-to-play state. Only one audio element plays at once; Voice Retry creates a new attempt without deleting the old WAV or changing text/response versions.

Resource measurements on RTX 5070 12,227 MiB:

| Scenario | VRAM idle | VRAM peak | Voice latency | Gemma latency | Result |
|---|---:|---:|---:|---:|---|
| Gemma only | about 8,603 MiB | 9,221 MiB (Phase 1.6) | — | 1.76–4.66 s | PASS |
| Voice F1 only | 975 MiB | 2,807 MiB | 4.006 s inference / 6.008 s wall | — | PASS |
| Gemma + Voice first load/generation | 8,684 MiB | 10,535 MiB | 11.534 s inference / 18.548 s wall | — | PASS |
| Gemma + Voice warm simultaneous | 10,612 MiB | 10,860 MiB | 1.407 s wall | 4.882 s | PASS |

Voice-only peak process Working Set was 2,379.1 MiB and Private Bytes 5,814.3 MiB. With both models resident, measured headroom remained about 1,367 MiB and no OOM occurred. The recommended Phase 2 strategy is **RESIDENT + SERIALIZED TTS**: keep Gemma resident, load Voice on first explicit use, serialize all TTS requests, and do not unload Gemma. Simultaneous short work succeeded, but routine scheduling should avoid intentionally overlapping GPU generation because headroom is limited. Future sentence/paragraph chunking may replace the current bounded single-WAV request; streaming TTS is not enabled.
