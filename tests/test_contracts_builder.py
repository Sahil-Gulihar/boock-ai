from src.models.state import GraphState
from src.graph.nodes import ingest_inputs, build_reference_conditioning_contract


def _base_state():
    return GraphState(
        job_id="job_test", book_version_id="boock_demo_visual_001", variant_id="variant_cinematic_default",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir="outputs",
    )


def test_build_reference_conditioning_contract_produces_typed_refs():
    state = ingest_inputs(_base_state())
    state = build_reference_conditioning_contract(state)
    contract = state.reference_conditioning_contract
    assert contract is not None

    mira_identity = [r for r in contract.identity_refs if r.entity_id == "mira"]
    assert len(mira_identity) == 1
    ref = mira_identity[0]
    assert ref.entity_type == "character"
    assert ref.display_name == "Mira"
    assert ref.source_asset_id == "mira_face_ref"
    assert ref.source_path == "provided_inputs/reference_assets/mira_face_ref.png"
    assert "face_identity" in ref.preserve_facets
    assert ref.family_id == "lockfam_character_mira_refpack_demo_v001"
    assert ref.required is True

    seal_props = [r for r in contract.prop_refs if r.entity_id == "black_seal"]
    assert len(seal_props) == 1
    assert seal_props[0].family_id == "lockfam_prop_black_seal_refpack_demo_v001"
