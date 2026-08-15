# SHION Desktop Companion — Phase H

## Technology decision

Phase H uses the existing Python 3.10 runtime with `tkinter` and a small
Windows `ctypes` adapter for `Shell_NotifyIcon`. PySide6, Qt, Electron,
WebView2 wrappers, Pillow and pystray are not present in the approved runtime.
Adding one of those frameworks would increase packaging and idle-resource cost
without improving the Phase H static presentation. Tk supplies a frameless,
transparent, DPI-aware window; the Win32 adapter supplies a native tray menu.

This choice supports Windows multi-monitor virtual coordinates and does not
introduce another model process. A future renderer can replace
`Static2DRenderer` behind `CharacterRenderer` without changing the backend
client or interaction controller. Live2D and 3D remain Owner Gates.

## Process and trust boundary

```text
Desktop Companion (display + Owner input)
             |
             | loopback HTTP only
             v
SHION Core :8765
  Conversation DB / Long-Term Memory / Generation Policy
  SelfCorrectionPolicy / Heretic / Voice / GpuResourceGate
```

The Companion never imports the model runtime, ConversationRepository, Memory
service, or Voice model. It creates and continues ordinary SHION sessions via
the existing API. A Desktop conversation is therefore visible from Web and
uses the same `character_id=shion`, Memory retrieval, pronunciation dictionary,
Voice Artifact Index, Nene V3 preset, and GPU queue. Backend and Companion
failures are process-isolated.

`BackendClient` rejects non-loopback base URLs. Phase H has no screen capture,
clipboard, filesystem discovery, keyboard hooks, microphone, browser-history,
Windows automation, credential access, or passive Memory source. The only
filesystem reads are registered Official SHION assets and Companion settings;
the only user-data write is the private settings file below `SHION_DATA_ROOT`.

## Components

- `desktop_companion.backend`: bounded loopback API adapter.
- `desktop_companion.settings`: atomic private JSON persistence and corrupt-file recovery.
- `desktop_companion.renderer`: official manifest/hash resolution and renderer boundary.
- `desktop_companion.tray`: dependency-free Windows notification icon and Owner actions.
- `desktop_companion.startup`: Owner-controlled HKCU Run registration; default OFF.
- `desktop_companion.app`: transparent presence, compact interaction panel and state projection.

The visible states are `IDLE`, `GENERATING`, `WAITING_FOR_GPU`, `SPEAKING`,
`OFFLINE`, and `ERROR`. Voice failure leaves the text response intact. When the
backend is offline the Companion remains visible with Retry and an explicit
Start SHION control; it never starts a second server automatically.

## Assets and rendering

The desktop renderer resolves `profile.json` and
`official/static_2d/asset_manifest.json`, requires Owner approval and verifies
the declared SHA-256 before loading `shion_panel.png`. The PNG is not rewritten,
resized on disk, regenerated, or copied into a new branded asset. Tk display
subsampling is presentation-only. The tray uses the Windows application icon;
Project SHION Logo remains a Deferred Owner Gate.

## Settings and recovery

Private settings: `%SHION_DATA_ROOT%/desktop_companion/settings.json`.

Stored fields are position, monitor scope, scale, visibility, always-on-top,
auto-play voice, start-with-Windows and current session. Invalid values recover
to conservative defaults. Position is clamped to the Windows virtual desktop so
topology changes retain a visible portion of SHION. Startup registration is
written only when the Owner toggles it in the tray and is OFF by default.
