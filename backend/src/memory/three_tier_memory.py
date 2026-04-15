class ThreeTierMemory:
    def __init__(self) -> None:
        self.index_layer = "MEMORY.MD"
        self.docs_layer = "markdown"
        self.transcript_layer = "json"

    def summary(self) -> dict:
        return {
            "index": self.index_layer,
            "documents": self.docs_layer,
            "transcripts": self.transcript_layer,
        }
