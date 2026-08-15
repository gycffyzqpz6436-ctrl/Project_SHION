from __future__ import annotations

import sys
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Project SHION Companion"


class StartupRegistration:
    def __init__(self, launcher: Path) -> None:
        self.launcher = launcher.resolve()

    @property
    def command(self) -> str:
        return f'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{self.launcher}"'

    def enabled(self) -> bool:
        if sys.platform != "win32": return False
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, VALUE_NAME)
                return value == self.command
        except FileNotFoundError:
            return False

    def set_enabled(self, enabled: bool) -> None:
        if sys.platform != "win32": raise RuntimeError("Windows startup registration is unavailable")
        import winreg
        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, self.command)
            return
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
