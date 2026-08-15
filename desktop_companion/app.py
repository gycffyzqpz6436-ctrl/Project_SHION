from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path

from .backend import BackendClient, BackendOffline
from .renderer import Static2DRenderer
from .settings import SettingsStore
from .startup import StartupRegistration
from .tray import WindowsTray


STATES = {
    "IDLE": ("READY", "#87d7b0"), "GENERATING": ("GENERATING", "#d8b4fe"),
    "WAITING_FOR_GPU": ("WAITING FOR GPU", "#f1c27d"), "SPEAKING": ("SPEAKING", "#82d7ff"),
    "OFFLINE": ("OFFLINE", "#a6a6b4"), "ERROR": ("ERROR", "#ff8f9c"),
}


def virtual_screen_bounds() -> tuple[int, int, int, int]:
    if sys.platform != "win32": return 0, 0, 1920, 1080
    import ctypes
    user32 = ctypes.windll.user32
    return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
            user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))


def clamp_position(x: int, y: int, width: int, height: int, bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, screen_width, screen_height = bounds
    right, bottom = left + screen_width, top + screen_height
    visible_width, visible_height = min(width, 96), min(height, 96)
    return (max(left - width + visible_width, min(x, right - visible_width)),
            max(top, min(y, bottom - visible_height)))


class DesktopCompanion:
    def __init__(self, repository_root: Path, data_root: Path, backend: BackendClient | None = None) -> None:
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.repository_root, self.data_root = repository_root.resolve(), data_root.resolve()
        self.backend = backend or BackendClient()
        self.store = SettingsStore(self.data_root); self.settings = self.store.load()
        self.startup = StartupRegistration(self.repository_root / "Start-SHION-Companion.ps1")
        self.commands: queue.Queue[str] = queue.Queue(); self.closing = False; self.state = "OFFLINE"
        self.sessions: list[dict] = []; self.session_by_title: dict[str, str] = {}; self.audio_files: list[Path] = []
        self.session_updated_at: dict[str, str] = {}
        self._drag_origin = None

        self._enable_dpi_awareness()
        self.root = tk.Tk(className="ProjectSHIONCompanion")
        self.root.title("SHION Desktop Companion"); self.root.overrideredirect(True)
        self.transparent = "#010203"; self.root.configure(bg=self.transparent)
        try: self.root.wm_attributes("-transparentcolor", self.transparent)
        except tk.TclError: pass
        self.root.wm_attributes("-topmost", self.settings.always_on_top)
        self.character = tk.Label(self.root, bg=self.transparent, bd=0, highlightthickness=0, cursor="hand2")
        self.character.pack()
        self.renderer = Static2DRenderer(self.root, self.character, self.repository_root, self.settings.scale)
        self.character.bind("<ButtonPress-1>", self._drag_start)
        self.character.bind("<B1-Motion>", self._drag_move)
        self.character.bind("<ButtonRelease-1>", self._drag_end)
        self._place_safely(self.settings.x, self.settings.y)

        self.panel = tk.Toplevel(self.root, class_="SHIONInteraction")
        self.panel.withdraw(); self.panel.title("SHION"); self.panel.configure(bg="#171320")
        self.panel.wm_attributes("-topmost", self.settings.always_on_top)
        self.panel.protocol("WM_DELETE_WINDOW", self.panel.withdraw)
        body = tk.Frame(self.panel, bg="#171320", padx=14, pady=12); body.pack(fill="both", expand=True)
        header = tk.Frame(body, bg="#171320"); header.pack(fill="x")
        tk.Label(header, text="SHION · 紫苑", fg="#f3eaff", bg="#171320", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.state_label = tk.Label(header, text="OFFLINE", fg=STATES["OFFLINE"][1], bg="#171320", font=("Segoe UI", 9, "bold")); self.state_label.pack(side="right")
        self.session_var = tk.StringVar(); self.session_box = ttk.Combobox(body, textvariable=self.session_var, state="readonly", width=45)
        self.session_box.pack(fill="x", pady=(10, 6)); self.session_box.bind("<<ComboboxSelected>>", self._select_session)
        conversation = tk.Frame(body, bg="#211a2d", padx=8, pady=8); conversation.pack(fill="both", expand=True)
        self.output = tk.Text(conversation, width=48, height=12, wrap="word", bg="#211a2d", fg="#f1ebf7",
            insertbackground="#ffffff", relief="flat", state="disabled", font=("Yu Gothic UI", 10))
        self.output.pack(fill="both", expand=True)
        self.input = tk.Text(body, width=48, height=3, wrap="word", bg="#241d30", fg="#ffffff", insertbackground="#ffffff", relief="flat")
        self.input.pack(fill="x", pady=(8, 6)); self.input.bind("<Control-Return>", self._send_event)
        actions = tk.Frame(body, bg="#171320"); actions.pack(fill="x")
        self.send_button = ttk.Button(actions, text="Send", command=self.send); self.send_button.pack(side="left")
        ttk.Button(actions, text="New", command=self.new_conversation).pack(side="left", padx=6)
        ttk.Button(actions, text="Open Web", command=self.open_web).pack(side="left")
        ttk.Button(actions, text="Exit", command=self.exit).pack(side="left", padx=6)
        self.voice_var = tk.BooleanVar(value=self.settings.auto_play_voice)
        ttk.Checkbutton(actions, text="Auto Voice", variable=self.voice_var, command=self._save_options).pack(side="right")
        self.offline = tk.Frame(body, bg="#171320")
        self.offline_message = tk.Label(self.offline, text="SHION Core is offline.", fg="#c9c1d1", bg="#171320"); self.offline_message.pack(side="left")
        ttk.Button(self.offline, text="Retry", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(self.offline, text="Start SHION", command=self.start_backend).pack(side="left")
        self.offline.pack(fill="x", pady=(8, 0))

        self.tray = WindowsTray({name: (lambda n=name: self.commands.put(n)) for name in ("show", "hide", "web", "top", "startup", "exit")},
            lambda name: self.settings.always_on_top if name == "top" else self.settings.start_with_windows)
        self.tray.start(); self.root.protocol("WM_DELETE_WINDOW", self.exit)
        if not self.settings.visible: self.renderer.hide()
        self.root.after(100, self._drain_commands); self.root.after(200, self.refresh)

    @staticmethod
    def _enable_dpi_awareness() -> None:
        if sys.platform != "win32": return
        import ctypes
        try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try: ctypes.windll.user32.SetProcessDPIAware()
            except Exception: pass

    def _place_safely(self, x: int, y: int) -> None:
        self.root.update_idletasks(); width = max(self.root.winfo_reqwidth(), 320); height = max(self.root.winfo_reqheight(), 420)
        x, y = clamp_position(x, y, width, height, virtual_screen_bounds())
        self.settings.x, self.settings.y, self.settings.monitor = x, y, "virtual-desktop"
        self.root.geometry(f"+{x}+{y}")

    def _drag_start(self, event) -> None: self._drag_origin = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
    def _drag_move(self, event) -> None:
        if self._drag_origin:
            sx, sy, x, y = self._drag_origin; self.root.geometry(f"+{x + event.x_root - sx}+{y + event.y_root - sy}")
    def _drag_end(self, event) -> None:
        if not self._drag_origin: return
        sx, sy, x, y = self._drag_origin; dx, dy = event.x_root - sx, event.y_root - sy; moved = abs(dx) + abs(dy)
        self._drag_origin = None; self._place_safely(x + dx, y + dy); self.store.save(self.settings)
        if moved < 8: self.toggle_panel()

    def toggle_panel(self) -> None:
        if self.panel.state() == "withdrawn":
            x = self.root.winfo_x() - 420 if self.root.winfo_x() > 500 else self.root.winfo_x() + self.root.winfo_width()
            self.panel.geometry(f"430x470+{x}+{max(20, self.root.winfo_y())}"); self.panel.deiconify(); self.input.focus_set()
        else: self.panel.withdraw()

    def _set_state(self, state: str, detail: str | None = None) -> None:
        self.state = state if state in STATES else "ERROR"; label, color = STATES[self.state]
        self.state_label.configure(text=detail or label, fg=color); self.renderer.set_state(self.state)
        if self.state == "OFFLINE": self.offline.pack(fill="x", pady=(8, 0))
        else: self.offline.pack_forget()

    def refresh(self) -> None:
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            status = self.backend.status(); sessions = self.backend.sessions(); state = self.backend.state(status)
            self.root.after(0, lambda: self._apply_refresh(state, sessions))
        except BackendOffline:
            self.root.after(0, lambda: self._set_state("OFFLINE"))
        if not self.closing: self.root.after(3000, self.refresh)

    def _apply_refresh(self, state: str, sessions: list[dict]) -> None:
        recovered = self.state == "OFFLINE" and state != "OFFLINE"
        self._set_state(state); self.sessions = sessions
        labels, mapping = [], {}
        updated = {}
        for item in sessions:
            label = f"{item.get('title', 'Conversation')} · {item['session_id'][:8]}"
            labels.append(label); mapping[label] = item["session_id"]
            updated[item["session_id"]] = item.get("updated_at", "")
        self.session_by_title = mapping; self.session_box["values"] = labels
        desired = next((label for label, sid in mapping.items() if sid == self.settings.session_id), labels[0] if labels else "")
        if desired:
            session_id = mapping[desired]
            changed = recovered or self.session_var.get() != desired or self.session_updated_at.get(session_id) != updated.get(session_id)
            if self.session_var.get() != desired:
                self.session_var.set(desired); self.settings.session_id = session_id; self.store.save(self.settings)
            self.session_updated_at = updated
            if changed: self.load_conversation()

    def _select_session(self, _event=None) -> None:
        self.settings.session_id = self.session_by_title.get(self.session_var.get()); self.store.save(self.settings); self.load_conversation()

    def load_conversation(self) -> None:
        session_id = self.settings.session_id
        if not session_id: return
        threading.Thread(target=self._load_worker, args=(session_id,), daemon=True).start()

    def _load_worker(self, session_id: str) -> None:
        try: data = self.backend.load_session(session_id)
        except Exception: return
        lines = []
        for item in data.get("messages", [])[-12:]:
            role = "Owner" if item.get("role") == "user" else "SHION"
            content = item.get("parts", item.get("content", ""))
            if isinstance(content, list): content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
            lines.append(f"{role}: {content}")
        self.root.after(0, lambda: self._set_output("\n\n".join(lines)))

    def _set_output(self, text: str) -> None:
        self.output.configure(state="normal"); self.output.delete("1.0", "end"); self.output.insert("end", text); self.output.see("end"); self.output.configure(state="disabled")

    def new_conversation(self) -> None:
        threading.Thread(target=self._new_worker, daemon=True).start()

    def _new_worker(self) -> None:
        try:
            result = self.backend.create_session("neutral"); self.settings.session_id = result["session_id"]; self.store.save(self.settings)
            self.root.after(0, self.refresh)
        except Exception as error: self.root.after(0, lambda: self._set_state("ERROR", str(error)[:40]))

    def _send_event(self, _event=None): self.send(); return "break"
    def send(self) -> None:
        text = self.input.get("1.0", "end").strip()
        if not text or self.state == "OFFLINE": return
        if not self.settings.session_id: self._new_and_send(text); return
        self.input.delete("1.0", "end"); self.send_button.configure(state="disabled"); self._set_state("GENERATING")
        threading.Thread(target=self._send_worker, args=(self.settings.session_id, text), daemon=True).start()

    def _new_and_send(self, text: str) -> None:
        def worker():
            try:
                result = self.backend.create_session("neutral"); self.settings.session_id = result["session_id"]; self.store.save(self.settings)
                self.root.after(0, lambda: self._begin_send(text))
            except Exception: self.root.after(0, lambda: self._set_state("OFFLINE"))
        threading.Thread(target=worker, daemon=True).start()

    def _begin_send(self, text: str) -> None: self.input.delete("1.0", "end"); self._set_state("GENERATING"); threading.Thread(target=self._send_worker, args=(self.settings.session_id, text), daemon=True).start()
    def _send_worker(self, session_id: str, text: str) -> None:
        try:
            result = self.backend.chat(session_id, text)
            self.root.after(0, lambda: self._set_output(f"Owner: {text}\n\nSHION: {result.get('response', '')}"))
            if self.voice_var.get() and result.get("message_id"):
                self.root.after(0, lambda: self._set_state("WAITING_FOR_GPU")); voice = self.backend.generate_voice(session_id, result["message_id"], int(result.get("version", 1)))
                self.root.after(0, lambda: self._set_state("SPEAKING")); self._play_audio(voice["audio_url"])
                self.root.after(max(500, int(float(voice.get("duration", 1)) * 1000)), self._finish_request)
            else:
                self.root.after(0, self._finish_request)
        except BackendOffline:
            self.root.after(0, lambda: (self._set_state("OFFLINE"), self.send_button.configure(state="normal")))
        except Exception as error:
            self.root.after(0, lambda: (self._set_state("ERROR", str(error)[:40]), self.send_button.configure(state="normal")))

    def _finish_request(self) -> None:
        self._set_state("IDLE"); self.send_button.configure(state="normal"); self.refresh()

    def _play_audio(self, url: str) -> None:
        if sys.platform != "win32": return
        import winsound
        data = self.backend.audio(url)
        if len(data) > 20 * 1024 * 1024: raise ValueError("Voice artifact exceeds playback limit")
        target = Path(tempfile.gettempdir()) / f"shion-companion-{os.getpid()}.wav"; target.write_bytes(data); self.audio_files.append(target)
        winsound.PlaySound(str(target), winsound.SND_FILENAME | winsound.SND_ASYNC)

    def _save_options(self) -> None: self.settings.auto_play_voice = self.voice_var.get(); self.store.save(self.settings)
    def open_web(self) -> None: webbrowser.open("http://127.0.0.1:8765/#/chat")
    def start_backend(self) -> None:
        try: self.backend.status(); return
        except BackendOffline: pass
        subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.repository_root / "Start-SHION.ps1"), "-NoBrowser"],
            cwd=self.repository_root, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)); self._set_state("OFFLINE", "STARTING SHION")
    def show(self) -> None: self.settings.visible = True; self.renderer.show(); self.store.save(self.settings)
    def hide(self) -> None: self.settings.visible = False; self.panel.withdraw(); self.renderer.hide(); self.store.save(self.settings)
    def toggle_top(self) -> None:
        self.settings.always_on_top = not self.settings.always_on_top; self.root.wm_attributes("-topmost", self.settings.always_on_top); self.panel.wm_attributes("-topmost", self.settings.always_on_top); self.store.save(self.settings)
    def toggle_startup(self) -> None:
        desired = not self.settings.start_with_windows; self.startup.set_enabled(desired); self.settings.start_with_windows = self.startup.enabled(); self.store.save(self.settings)
    def _drain_commands(self) -> None:
        actions = {"show": self.show, "hide": self.hide, "web": self.open_web, "top": self.toggle_top, "startup": self.toggle_startup, "exit": self.exit}
        while True:
            try: actions[self.commands.get_nowait()]()
            except queue.Empty: break
        if not self.closing: self.root.after(100, self._drain_commands)
    def exit(self) -> None:
        if self.closing: return
        self.closing = True; self.settings.x, self.settings.y = self.root.winfo_x(), self.root.winfo_y(); self.store.save(self.settings); self.tray.stop()
        for target in self.audio_files:
            try: target.unlink(missing_ok=True)
            except OSError: pass
        self.root.after(50, self.root.destroy)
    def run(self) -> None: self.root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project SHION Desktop Companion")
    parser.add_argument("--data-root", default=os.environ.get("SHION_DATA_ROOT", r"D:\AI\Project_SHION"))
    parser.add_argument("--backend", default="http://127.0.0.1:8765")
    parser.add_argument("--open-panel", action="store_true", help=argparse.SUPPRESS)
    return parser


def main() -> None:
    args = build_parser().parse_args(); root = Path(__file__).resolve().parents[1]
    companion = DesktopCompanion(root, Path(args.data_root), BackendClient(args.backend))
    if args.open_panel: companion.root.after(250, companion.toggle_panel)
    companion.run()


if __name__ == "__main__": main()
