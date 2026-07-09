from src.models.state import GraphState
from src.graph.nodes import (
    ingest_inputs, retrieve_visual_memory, build_reference_conditioning_contract,
    build_reference_lock_family_manifest, select_generation_strategy,
)


class FakeMem0Client:
    def __init__(self, seed_store=None):
        self.store = seed_store if seed_store is not None else {}

    def add(self, messages, user_id, infer=True):
        self.store.setdefault(user_id, []).append(messages)

    def search(self, query, user_id, limit=10):
        return {"results": [{"memory": m} for m in self.store.get(user_id, [])]}


def _base_state():
    return GraphState(
        job_id="job_drift", book_version_id="boock_demo_visual_001", variant_id="variant_cinematic_default",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir="outputs",
    )


def test_family_id_incorporates_reference_pack_id():
    from src.graph.nodes import _family_id
    assert _family_id("character", "mira", "refpack_demo_v001") == "lockfam_character_mira_refpack_demo_v001"
    assert _family_id("character", "mira", "refpack_demo_v002") == "lockfam_character_mira_refpack_demo_v002"


def test_no_drift_block_on_first_run_with_fresh_memory():
    from src.memory.mem0_adapter import VisualMemoryAdapter
    memory_adapter = VisualMemoryAdapter(memory_client=FakeMem0Client())

    state = ingest_inputs(_base_state())
    state = retrieve_visual_memory(state, memory_adapter)
    state = build_reference_conditioning_contract(state)
    state = build_reference_lock_family_manifest(state, memory_adapter)
    state = select_generation_strategy(state)

    for contract in state.scene_render_contracts.values():
        assert contract.blocked is False


def test_family_drift_across_runs_blocks_scene_without_any_manual_corruption():
    """The hard block must be reachable through realistic operation: a second
    run against an updated/rotated reference pack for the same entity_id,
    with no test-injected corruption of any TypedRef."""
    from src.memory.mem0_adapter import VisualMemoryAdapter

    shared_store: dict[str, list[str]] = {}
    memory_adapter_run1 = VisualMemoryAdapter(memory_client=FakeMem0Client(shared_store))

    # Run 1: seeds memory with the approved family_id for this reference pack.
    state1 = ingest_inputs(_base_state())
    state1 = retrieve_visual_memory(state1, memory_adapter_run1)
    state1 = build_reference_conditioning_contract(state1)
    state1 = build_reference_lock_family_manifest(state1, memory_adapter_run1)

    # Run 2: same memory store, but the reference pack was rotated to a new
    # reference_pack_id for the same entities (a realistic operational event,
    # not manual test corruption of a TypedRef).
    memory_adapter_run2 = VisualMemoryAdapter(memory_client=FakeMem0Client(shared_store))
    state2 = ingest_inputs(_base_state())
    state2.external_reference_pack.reference_pack_id = "refpack_demo_v002_ROTATED"
    state2 = retrieve_visual_memory(state2, memory_adapter_run2)
    state2 = build_reference_conditioning_contract(state2)
    state2 = build_reference_lock_family_manifest(state2, memory_adapter_run2)
    state2 = select_generation_strategy(state2)

    scene_001 = state2.scene_render_contracts["scene_001_mira_closeup"]
    assert scene_001.blocked is True
    assert scene_001.block_entity_id == "mira"
    assert "drift" in scene_001.block_reason.lower()
