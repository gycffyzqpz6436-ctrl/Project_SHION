# SHION Future Architecture

Status: Phase 1 foundation (2026-08-09)

This document owns **how the system is structured**. Planned features, sequencing,
and approval gates are owned by the
[Project SHION Future Roadmap](../roadmap/project_shion_future_roadmap.md).

## Design boundary

SHION is an application-level personal companion. A conversation LLM is one
replaceable reasoning component; it is not the complete SHION system.

```mermaid
flowchart TD
    U["Owner / UI"] --> API["Local API boundary"]
    API --> CORE["SHION Runtime"]
    CORE --> ORCH["Orchestrator"]
    ORCH --> CM["ConversationModel"]
    ORCH --> STM["Short-term session context"]
    ORCH -. disabled .-> LTM["Long-term memory"]
    ORCH -. validated requests only .-> TR["Tool Registry"]
    TR -. disabled .-> V["Vision"]
    TR -. disabled .-> I["Image generation"]
    TR -. disabled .-> W["Web"]
    TR -. disabled .-> VO["Voice"]
    TR -. disabled .-> L["Local tools"]
    CORE -. future state .-> AV["Avatar / Live2D"]
```

The solid path is implemented. Dotted capabilities are interfaces or explicit
disabled entries only. They do not load models, access the network, or execute
tools.

## Phase 1 repository responsibilities

```text
app/
  server.py                 localhost HTTP and static-file boundary
  core/
    shion_runtime.py        lifecycle and application coordination
    orchestrator.py         conversation-first orchestration seam
    session.py              volatile short-term chat history
    state.py                runtime state vocabulary
  models/
    conversation_model.py   common ConversationModel protocol
    registry.py             server-side allowlist and public projection
    loader.py               offline model-adapter construction
  runtime/
    model_runtime.py        compatibility adapter for current Transformers runtime
  memory/
    interface.py            long-term memory contract
    long_term.py            disabled implementation
  tools/
    interface.py            capability result and tool contract
    registry.py             default-deny registry and disabled capabilities
  static/
    assets/shion/            replaceable avatar assets
    index.html, styles.css, app.js
```

`app.runtime.model_runtime.LocalModelRuntime` remains in place as a compatibility
adapter. Moving its tokenizer/model-specific implementation is deferred until a
separate migration can preserve the already-validated Gemma, Mistral, Qwen, NF4,
EOS and non-thinking behavior.

## Request flow

1. `server.py` accepts only a localhost request with a bounded JSON body.
2. `ShionRuntime` obtains the in-memory short-term history.
3. `ShionOrchestrator` selects the conversation-only path in Phase 1.
4. The allowlisted `ConversationModel` produces a response.
5. The current turn is retained in volatile session memory.

Future tool routing must create a structured request and pass it through the tool
registry and capability-specific security validation. Conversation-model output
must never be forwarded directly to `eval`, `exec`, a shell, PowerShell, a browser,
the filesystem, or the network.

## Model abstraction

UI and session code depend on an alias and the `ConversationModel` protocol, not a
Transformers class. The registry/loader/runtime adapter owns model class selection,
tokenizer loading, chat-template options, thinking mode, EOS IDs, quantization and
generation defaults. Client-provided model paths remain prohibited.

## Memory

Phase F activates the local Owner-controlled implementation behind the existing Memory boundary. Automatic promotion remains OFF: normal conversation, assistant output, external documents, and tools cannot silently mutate approved Owner Memory. Deterministic retrieval is the current adapter; vectors, cloud synchronization, Desktop Companion access, cross-character sharing, and external knowledge remain future Owner Gates. The detailed contract is in `shion_long_term_memory.md`.

- Short-term memory is the current `(session, mode)` conversation context and is
  cleared on New Chat or model switch.
- Long-term memory is a separate future service for preferences, relationship
  history, events and SHION memories. It is currently unavailable and performs no
  persistence or retrieval.

Chat history must not become long-term memory merely because a storage backend is
added later. Retention, consent, deletion and retrieval policies belong at the
long-term-memory boundary.

## Tool and security architecture

Vision, image generation, web, voice and local tools are registered as disabled.
Unknown or disabled invocations return `ToolResult(available=False)` without
calling an implementation. Enabling a future tool requires all of:

1. explicit Owner configuration;
2. a typed request schema;
3. capability-specific allowlists and validation;
4. bounded resource and timeout policy;
5. safe result serialization back to the orchestrator;
6. tests proving no direct model-to-capability path.

External network access remains absent. The server continues to bind exclusively
to `127.0.0.1`.

## UI and message evolution

The Phase 1 UI keeps the established dark-purple vertical chat and adds SHION
identity, an avatar asset boundary, copy controls, a collapsible Model Info panel,
an Experimental badge, a reserved desktop conversation rail, and safe generation
stopping. The generating label is presentation state, not internal reasoning or
chain-of-thought.

The frontend normalizes current text into content parts:

```json
[{"type": "text", "text": "..."}]
```

This creates a future rendering seam for `image`, `file`, and `tool_result` parts
without changing the current API response. Composer slots are reserved for later
attachment and microphone controls. No upload or voice behavior exists now.

Avatar assets live under `app/static/assets/shion/`. The current SVG can be replaced
by a portrait while keeping the message/header component. A later Avatar adapter
can map SHION state to portrait expressions or Live2D motions; it must not be
coupled to the conversation model class.

The Workspace now treats the SVG as a missing-asset fallback. Official Character
assets live under a versioned Character root and resolve through a profile plus
manifest. SHION's current Owner-approved registration is
`official_static_2d_v1`: Avatar, Panel and Master remain separate semantic roles.
`CharacterRenderer` consumes an asset set and bounded presentation state, so a
future Live2D/3D renderer or another Character profile does not require changes
to Conversation or Voice backends.

## Stop generation

The browser changes Send to Stop while a request is generating. `/api/stop` sets a
session-scoped cancellation event. A Transformers stopping criterion observes it
between token steps, returns the partial text, and leaves the model loaded so the
next turn can continue. Stop does not kill a process or unload model weights.

## Future capability architecture overview

- Vision: validated image upload -> vision adapter -> structured observation ->
  orchestrator -> conversation response.
- Image generation: structured prompt request -> isolated generator -> safe local
  artifact reference -> multipart message rendering.
- Voice: microphone input and speech output adapters outside conversation-model
  logic, both explicitly enabled by the Owner.
- Web: restricted fetch/search tool with domain, network, timeout and content
  validation; never direct LLM network access.
- Smartphone: keep UI responsive and separate network exposure from UI/runtime.
- Live2D: presentation adapter consumes explicit SHION expression/state events and
  never receives unrestricted tool authority.

### Desktop Companion client boundary

A future Desktop SHION Companion is an independent Windows client and process.
It is not the browser-based Floating Assistant and must not depend on Dashboard
DOM state or browser storage. Both presentation surfaces may share only stable
local contracts backed by Conversation, Voice and Character services.

```mermaid
flowchart LR
    WEB["SHION Dashboard"] --> FLOAT["Web Floating Assistant"]
    FLOAT --> API["Local SHION application API"]
    DESK["Desktop Companion"] --> API
    DESK --> PB["Owner permission broker (default OFF)"]
    DESK --> RI["CharacterRenderer interface"]
    RI --> R2["Official 2D renderer"]
    RI -. future replacement .-> R3["3D renderer"]
    API --> CONV["Conversation backend"]
    API --> VOICE["Voice backend"]
    API --> CHAR["Character state backend"]
```

The Companion may later provide an always-on-top Avatar window, Mini Chat, Nene
Voice, notifications and an explicit Dashboard launcher. Desktop observation is
not implicit in those features. Active application, window title, screen capture
and selected-text access are separate Owner permissions, default OFF, mediated by
the broker and revocable independently. Protected authentication and secret
surfaces require deny/redaction rules, visible capture indication and bounded
retention. The renderer receives presentation state only and has no desktop or
tool authority.

This is an architecture extension point only. Phase 1 adds no executable,
background agent, global hook, screen capture, UI Automation, clipboard monitor,
startup task or Windows permission request.

Network stages are intentionally separate:

1. Current: localhost (`127.0.0.1`) only.
2. Future Owner-reviewed stage: authenticated LAN binding.
3. Future Owner-reviewed stage: authenticated Tailscale access.

No Stage 2 or Stage 3 networking is implemented by this change.

## Migration phases

- Phase 1 (this change): extract core/session/registry/orchestrator/tool/memory
  boundaries, retain runtime compatibility, polish UI.
- Phase 2: move model-family details behind explicit adapters and split HTTP route
  handlers into API modules, with parity tests for every approved model.
- Phase 3: add only Owner-approved capability implementations, persistence and
  presentation adapters one boundary at a time.
