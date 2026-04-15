class RetrievalSwarm:
    def run(self, query: str) -> dict:
        return {
            "query": query,
            "sources": [
                "data/confluence",
                "data/runbooks",
                "data/incidents",
            ],
        }
