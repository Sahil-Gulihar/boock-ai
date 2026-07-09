import tempfile
from src.models.state import GraphState
from src.models.scene_contract import SceneRenderContract
from src.storage.artifact_store import LocalArtifactStore
from src.providers.mock_provider import MockProvider
from src.graph.nodes import (
    ingest_inputs, build_reference_conditioning_contract,
    render_scene_images, validate_scene_consistency, decide_pass_repair_or_block,
)


def _state_with_one_blocked_one_ok(tmp_dir):
    state = GraphState(
        job_id="job_qa", book_version_id="b", variant_id="v",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir=str(tmp_dir),
    )
    state = ingest_inputs(state)
    state = build_reference_conditioning_contract(state)
    state.scene_render_contracts = {
        "scene_ok": SceneRenderContract(
            scene_id="scene_ok", prompt="p", negative_prompt="n", style_route="grounded_mythic_cinematic",
            required_character_refs=["mira"], required_prop_refs=[], required_location_refs=["ruined_watchtower"],
            family_ids=["lockfam_character_mira_v001"], view_ids=["face_front_close"], provider="mock", seed=1,
        ),
        "scene_blocked": SceneRenderContract(
            scene_id="scene_blocked", prompt="p", negative_prompt="n", style_route="grounded_mythic_cinematic",
            required_character_refs=["mira"], required_prop_refs=[], required_location_refs=["ruined_watchtower"],
            family_ids=[], view_ids=[], provider="mock", seed=2,
            blocked=True, block_reason="Mixed family_id refs for entity 'mira'",
        ),
    }
    return state


def test_render_skips_blocked_scenes():
    tmp_dir = tempfile.mkdtemp()
    state = _state_with_one_blocked_one_ok(tmp_dir)
    state = render_scene_images(
        state,
        provider=MockProvider(),
        artifact_store=LocalArtifactStore(base_dir=state.output_dir),
    )
    assert "scene_ok" in state.scene_images
    assert "scene_blocked" not in state.scene_images


def test_qa_report_flags_blocked_scene_and_repair_ticket_created():
    tmp_dir = tempfile.mkdtemp()
    state = _state_with_one_blocked_one_ok(tmp_dir)
    store = LocalArtifactStore(base_dir=state.output_dir)
    state = render_scene_images(state, provider=MockProvider(), artifact_store=store)
    state = validate_scene_consistency(state, artifact_store=store)

    blocked_result = next(r for r in state.qa_report.scene_results if r.scene_id == "scene_blocked")
    assert blocked_result.verdict == "blocked"
    ok_result = next(r for r in state.qa_report.scene_results if r.scene_id == "scene_ok")
    assert ok_result.verdict == "approved"

    state = decide_pass_repair_or_block(state)
    assert len(state.repair_tickets.tickets) == 1
    ticket = state.repair_tickets.tickets[0]
    assert ticket.scene_id == "scene_blocked"
    assert ticket.severity == "blocker"
    assert ticket.rerun_from_node == "build_reference_lock_family_manifest"
