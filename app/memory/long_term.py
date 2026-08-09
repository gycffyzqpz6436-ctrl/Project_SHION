class DisabledLongTermMemory:
    available = False

    def retrieve(self, query: str) -> list[dict]:
        return []
