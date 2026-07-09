from __future__ import annotations
import os


def _build_default_client():
    from mem0 import Memory

    config = {
        "llm": {
            "provider": "openai",
            "config": {"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY", "")},
        },
        "vector_store": {
            "provider": "chroma",
            "config": {"collection_name": "boock_visual_memory", "path": "chroma_db"},
        },
    }
    return Memory.from_config(config)


class VisualMemoryAdapter:
    """Isolates mem0 behind Boock's own get/save-fact interface.

    mem0's LLM is used only internally by mem0 for its own fact
    extraction/dedup step -- it never sees or produces image content.
    """

    def __init__(self, memory_client=None):
        self.client = memory_client or _build_default_client()

    def save_fact(self, entity_id: str, fact: str) -> None:
        self.client.add(fact, user_id=entity_id)

    def get_facts(self, entity_id: str) -> list[str]:
        result = self.client.search(query="visual identity facts", user_id=entity_id, limit=25)
        return [item["memory"] for item in result.get("results", [])]
