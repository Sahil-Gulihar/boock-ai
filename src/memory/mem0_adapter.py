from __future__ import annotations
import os


class _LocalFallbackMemoryClient:
    """Same add()/search() shape as mem0's client, backed by an in-process dict.

    Used automatically when OPENAI_API_KEY isn't set, since mem0's OpenAI-backed
    LLM provider raises at construction time (not just at call time) without one.
    This keeps the CLI/API/pytest runnable with zero external API keys, per the
    assignment's hard rule, while still using the real mem0 SDK whenever a key
    is configured (e.g. for the real sample run).
    """

    def __init__(self):
        self._store: dict[str, list[str]] = {}

    def add(self, messages, user_id, infer=True):
        self._store.setdefault(user_id, []).append(messages)

    def search(self, query, user_id, limit=10):
        facts = self._store.get(user_id, [])
        return {"results": [{"memory": m} for m in facts]}


def _build_default_client():
    if not os.environ.get("OPENAI_API_KEY"):
        return _LocalFallbackMemoryClient()

    from mem0 import Memory

    config = {
        "llm": {
            "provider": "openai",
            "config": {"model": "gpt-4o-mini", "api_key": os.environ["OPENAI_API_KEY"]},
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
