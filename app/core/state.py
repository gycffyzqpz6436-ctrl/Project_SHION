from enum import Enum


class RuntimeState(str, Enum):
    STARTING = "Starting"
    LOADING = "Loading model"
    READY = "Ready"
    GENERATING = "Generating"
    ERROR = "Error"

    def __str__(self) -> str:
        return self.value
