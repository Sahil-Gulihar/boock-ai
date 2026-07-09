from src.models.state import GraphState
from src.models.scene_contract import SceneRenderContract
from src.models.qa import QACheckResult, SceneQAResult, QAReport
from src.graph.nodes import ingest_inputs, decide_pass_repair_or_block


def test_decide_pass_repair_or_block_generates_ticket_for_missing_view():
    state = GraphState(
        job_id="job_repair", book_version_id="b", variant_id="v",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir="outputs",
    )
    state = ingest_inputs(state)
    state.scene_render_contracts = {"scene_002_two_shot": SceneRenderContract(
        scene_id="scene_002_two_shot", prompt="p", negative_prompt="n", style_route="grounded_mythic_cinematic",
        required_character_refs=["mira"], required_prop_refs=[], required_location_refs=["ruined_watchtower"],
        family_ids=[], view_ids=[], provider="mock", seed=1,
    )}
    check = QACheckResult(
        check_name="required_characters_present", passed=False, severity="blocker",
        message="Mira reference family missing fullbody_three_quarter view",
    )
    state.qa_report = QAReport(
        job_id="job_repair",
        scene_results=[SceneQAResult(scene_id="scene_002_two_shot", checks=[check], verdict="needs_repair")],
        overall_verdict="needs_repair",
    )
    state = decide_pass_repair_or_block(state)
    assert len(state.repair_tickets.tickets) == 1
    ticket = state.repair_tickets.tickets[0]
    assert ticket.scene_id == "scene_002_two_shot"
    assert ticket.entity_id == "mira"
    assert "missing" in ticket.problem.lower()
