"""Windows Desktop SHION Companion frontend.

The package is deliberately a client of SHION Core.  It never imports or
constructs the LLM, Memory, or Voice runtimes.
"""

from .backend import BackendClient, BackendOffline
from .settings import CompanionSettings, SettingsStore

__all__ = ["BackendClient", "BackendOffline", "CompanionSettings", "SettingsStore"]
