from src.models.state import GraphState
from src.graph.nodes import (
    ingest_inputs, retrieve_visual_memory, build_reference_conditioning_contract,
    build_reference_lock_family_manifest,
)
from src.memory.mem0_adapter import VisualMemoryAdapter


class FakeMem0Client:
    def __init__(self):
        self.store = {}

    def add(self, messages, user_id, infer=True):
        self.store.setdefault(user_id, []).append(messages)

    def search(self, query, user_id, limit=10):
        return {"results": [{"memory": m} for m in self.store.get(user_id, [])]}


def _base_state():
    return GraphState(
        job_id="job_mem_coverage", book_version_id="boock_demo_visual_001", variant_id="variant_cinematic_default",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir="outputs",
    )


def test_retrieve_visual_memory_seeds_location_identity_markers():
    memory_adapter = VisualMemoryAdapter(memory_client=FakeMem0Client())
    state = ingest_inputs(_base_state())
    state = retrieve_visual_memory(state, memory_adapter)

    assert "ruined_watchtower" in state.memory_facts
    facts = state.memory_facts["ruined_watchtower"]
    assert any("broken stone arch" in f for f in facts)
    assert any("rain puddles" in f for f in facts)


def test_build_reference_lock_family_manifest_saves_approved_family_id_fact():
    memory_adapter = VisualMemoryAdapter(memory_client=FakeMem0Client())
    state = ingest_inputs(_base_state())
    state = retrieve_visual_memory(state, memory_adapter)
    state = build_reference_conditioning_contract(state)
    state = build_reference_lock_family_manifest(state, memory_adapter)

    mira_facts = memory_adapter.get_facts("mira")
    assert any(f.startswith("approved_family_id=lockfam_character_mira_") for f in mira_facts)
