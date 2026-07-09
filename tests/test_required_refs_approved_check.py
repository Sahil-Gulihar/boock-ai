from src.models.state import GraphState
from src.models.scene_contract import SceneRenderContract
from src.storage.artifact_store import LocalArtifactStore
from src.providers.mock_provider import MockProvider
from src.graph.nodes import (
    ingest_inputs, build_reference_conditioning_contract,
    render_scene_images, validate_scene_consistency,
)


def test_required_refs_approved_check_passes_for_approved_refs(tmp_path):
    state = ingest_inputs(GraphState(
        job_id="job_approved", book_version_id="b", variant_id="v",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir=str(tmp_path),
    ))
    state = build_reference_conditioning_contract(state)
    state.scene_render_contracts = {
        "scene_ok": SceneRenderContract(
            scene_id="scene_ok", prompt="p", negative_prompt="n", style_route="grounded_mythic_cinematic",
            required_character_refs=["mira"], required_prop_refs=[], required_location_refs=["ruined_watchtower"],
            family_ids=[], view_ids=[], provider="mock", seed=1,
        ),
    }
    store = LocalArtifactStore(base_dir=str(tmp_path))
    state = render_scene_images(state, provider=MockProvider(), artifact_store=store)
    state = validate_scene_consistency(state, artifact_store=store)

    result = state.qa_report.scene_results[0]
    check = next(c for c in result.checks if c.check_name == "required_refs_approved")
    assert check.passed is True


def test_required_refs_approved_check_blocks_unapproved_ref(tmp_path):
    state = ingest_inputs(GraphState(
        job_id="job_unapproved", book_version_id="b", variant_id="v",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir=str(tmp_path),
    ))
    state = build_reference_conditioning_contract(state)
    # Simulate an optional (required=False) reference that never got approved.
    for ref in state.reference_conditioning_contract.identity_refs:
        if ref.entity_id == "mira":
            ref.approval_state = "qa_pending"

    state.scene_render_contracts = {
        "scene_needs_approval": SceneRenderContract(
            scene_id="scene_needs_approval", prompt="p", negative_prompt="n", style_route="grounded_mythic_cinematic",
            required_character_refs=["mira"], required_prop_refs=[], required_location_refs=["ruined_watchtower"],
            family_ids=[], view_ids=[], provider="mock", seed=1,
        ),
    }
    store = LocalArtifactStore(base_dir=str(tmp_path))
    state = render_scene_images(state, provider=MockProvider(), artifact_store=store)
    state = validate_scene_consistency(state, artifact_store=store)

    result = state.qa_report.scene_results[0]
    check = next(c for c in result.checks if c.check_name == "required_refs_approved")
    assert check.passed is False
    assert check.severity == "blocker"
    assert check.entity_id == "mira"
    assert result.verdict == "needs_repair"
