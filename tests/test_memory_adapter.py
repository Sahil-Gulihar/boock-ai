from src.memory.mem0_adapter import VisualMemoryAdapter


class FakeMem0Client:
    def __init__(self):
        self.store = {}
        self.add_calls = []

    def add(self, messages, user_id, infer=True):
        self.add_calls.append({"messages": messages, "user_id": user_id, "infer": infer})
        self.store.setdefault(user_id, []).append(messages)

    def search(self, query, user_id, limit=10):
        facts = self.store.get(user_id, [])
        return {"results": [{"memory": m} for m in facts]}


def test_save_and_retrieve_facts():
    client = FakeMem0Client()
    adapter = VisualMemoryAdapter(memory_client=client)

    adapter.save_fact("mira", "Mira's hair is dark curly shoulder-length")
    adapter.save_fact("mira", "Mira's cloak is deep green with a brass clasp")

    facts = adapter.get_facts("mira")
    assert "Mira's hair is dark curly shoulder-length" in facts
    assert "Mira's cloak is deep green with a brass clasp" in facts


def test_get_facts_empty_for_unknown_entity():
    adapter = VisualMemoryAdapter(memory_client=FakeMem0Client())
    assert adapter.get_facts("nobody") == []


def test_save_fact_disables_mem0_llm_inference():
    """Facts we save are already structured (e.g. 'approved_family_id=...')
    and must be retrievable verbatim for exact-match parsing downstream
    (see select_generation_strategy's drift detection) -- infer=True would
    let mem0's own LLM paraphrase them into free text, silently breaking
    that parsing against a real mem0 backend."""
    client = FakeMem0Client()
    adapter = VisualMemoryAdapter(memory_client=client)
    adapter.save_fact("mira", "approved_family_id=lockfam_character_mira_refpack_demo_v001")
    assert client.add_calls[0]["infer"] is False
