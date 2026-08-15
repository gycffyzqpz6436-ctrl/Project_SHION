from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes


class WindowsTray:
    """Small dependency-free Shell_NotifyIcon adapter."""

    WM_APP = 0x8000
    WM_TRAY = WM_APP + 17
    WM_COMMAND, WM_DESTROY = 0x0111, 0x0002
    WM_RBUTTONUP, WM_LBUTTONDBLCLK = 0x0205, 0x0203
    NIM_ADD, NIM_DELETE = 0, 2
    NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
    MF_STRING, MF_CHECKED, TPM_RIGHTBUTTON = 0, 8, 2
    ID_SHOW, ID_HIDE, ID_WEB, ID_TOP, ID_STARTUP, ID_EXIT = range(1001, 1007)

    def __init__(self, actions: dict[str, callable], checked: callable) -> None:
        self.actions, self.checked = actions, checked
        self.thread: threading.Thread | None = None
        self.hwnd = None
        self.ready = threading.Event()
        self._wndproc_ref = None

    def start(self) -> None:
        if sys.platform != "win32": return
        self.thread = threading.Thread(target=self._run, name="SHIONTray", daemon=True)
        self.thread.start(); self.ready.wait(5)

    def stop(self) -> None:
        if self.hwnd: ctypes.windll.user32.PostMessageW(self.hwnd, self.WM_DESTROY, 0, 0)

    def _run(self) -> None:
        user32, shell32, kernel32 = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT

        class WNDCLASS(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uTimeoutOrVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON)]

        def dispatch(name: str) -> None:
            action = self.actions.get(name)
            if action: action()

        def show_menu(hwnd) -> None:
            menu = user32.CreatePopupMenu()
            items = [(self.ID_SHOW, "Show SHION", "show"), (self.ID_HIDE, "Hide SHION", "hide"),
                (self.ID_WEB, "Open SHION Web", "web"), (self.ID_TOP, "Always on Top", "top"),
                (self.ID_STARTUP, "Start with Windows", "startup"), (self.ID_EXIT, "Exit", "exit")]
            for command, label, name in items:
                flags = self.MF_STRING | (self.MF_CHECKED if name in {"top", "startup"} and self.checked(name) else 0)
                user32.AppendMenuW(menu, flags, command, label)
            point = wintypes.POINT(); user32.GetCursorPos(ctypes.byref(point)); user32.SetForegroundWindow(hwnd)
            command = user32.TrackPopupMenu(menu, self.TPM_RIGHTBUTTON | 0x0100, point.x, point.y, 0, hwnd, None)
            user32.DestroyMenu(menu)
            names = {item[0]: item[2] for item in items}
            if command in names: dispatch(names[command])

        @WNDPROC
        def wndproc(hwnd, message, wparam, lparam):
            if message == self.WM_TRAY:
                if lparam == self.WM_RBUTTONUP: show_menu(hwnd)
                elif lparam == self.WM_LBUTTONDBLCLK: dispatch("show")
                return 0
            if message == self.WM_DESTROY:
                shell32.Shell_NotifyIconW(self.NIM_DELETE, ctypes.byref(icon)); user32.PostQuitMessage(0); return 0
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        self._wndproc_ref = wndproc
        name = "ProjectSHIONCompanionTray"
        instance = kernel32.GetModuleHandleW(None)
        cls = WNDCLASS(0, wndproc, 0, 0, instance, None, None, None, None, name)
        user32.RegisterClassW(ctypes.byref(cls))
        self.hwnd = user32.CreateWindowExW(0, name, name, 0, 0, 0, 0, 0, None, None, instance, None)
        icon = NOTIFYICONDATA(); icon.cbSize = ctypes.sizeof(icon); icon.hWnd = self.hwnd; icon.uID = 1
        icon.uFlags = self.NIF_MESSAGE | self.NIF_ICON | self.NIF_TIP; icon.uCallbackMessage = self.WM_TRAY
        icon.hIcon = user32.LoadIconW(None, 32512); icon.szTip = "Project SHION Companion"
        shell32.Shell_NotifyIconW(self.NIM_ADD, ctypes.byref(icon)); self.ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message)); user32.DispatchMessageW(ctypes.byref(message))
