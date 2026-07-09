from src.models.state import GraphState
from src.graph.nodes import (
    ingest_inputs, build_reference_conditioning_contract,
    build_reference_lock_family_manifest, select_generation_strategy,
)


def _state_through_lock_family():
    state = GraphState(
        job_id="job_test_block", book_version_id="boock_demo_visual_001", variant_id="variant_cinematic_default",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir="outputs",
    )
    state = ingest_inputs(state)
    state = build_reference_conditioning_contract(state)
    state = build_reference_lock_family_manifest(state)
    return state


def test_mixed_family_refs_for_same_entity_block_the_scene():
    state = _state_through_lock_family()

    # Simulate a corrupted contract: two refs for "mira" carrying different family_ids.
    mira_refs = [r for r in state.reference_conditioning_contract.identity_refs if r.entity_id == "mira"]
    assert len(mira_refs) == 1
    duplicate = mira_refs[0].model_copy(update={"family_id": "lockfam_character_mira_v002_ROGUE", "view_id": "fullbody_front"})
    state.reference_conditioning_contract.identity_refs.append(duplicate)

    state = select_generation_strategy(state)

    scene_002 = state.scene_render_contracts["scene_002_two_shot"]
    assert scene_002.blocked is True
    assert "mira" in scene_002.block_reason
    assert "family" in scene_002.block_reason.lower()

    scene_001 = state.scene_render_contracts["scene_001_mira_closeup"]
    assert scene_001.blocked is True  # mira also appears in scene_001
