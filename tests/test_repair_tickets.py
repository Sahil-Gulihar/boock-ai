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


def test_decide_pass_repair_or_block_emits_one_ticket_per_failing_entity_and_check():
    """Two independent blocker failures on one scene, naming different
    entities, must each produce their own correctly-attributed ticket --
    not just one ticket for the first check/entity found."""
    state = GraphState(
        job_id="job_repair_multi", book_version_id="b", variant_id="v",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir="outputs",
    )
    state = ingest_inputs(state)
    state.scene_render_contracts = {"scene_002_two_shot": SceneRenderContract(
        scene_id="scene_002_two_shot", prompt="p", negative_prompt="n", style_route="grounded_mythic_cinematic",
        required_character_refs=["mira", "arin"], required_prop_refs=["black_seal"],
        required_location_refs=["ruined_watchtower"],
        family_ids=[], view_ids=[], provider="mock", seed=1,
    )}
    checks = [
        QACheckResult(
            check_name="required_characters_present", passed=False, severity="blocker",
            message="missing character ref for 'arin'", entity_id="arin",
        ),
        QACheckResult(
            check_name="required_props_present", passed=False, severity="blocker",
            message="missing prop ref for 'black_seal'", entity_id="black_seal",
        ),
    ]
    state.qa_report = QAReport(
        job_id="job_repair_multi",
        scene_results=[SceneQAResult(scene_id="scene_002_two_shot", checks=checks, verdict="needs_repair")],
        overall_verdict="needs_repair",
    )
    state = decide_pass_repair_or_block(state)

    assert len(state.repair_tickets.tickets) == 2
    entity_ids = {t.entity_id for t in state.repair_tickets.tickets}
    assert entity_ids == {"arin", "black_seal"}
    for ticket in state.repair_tickets.tickets:
        assert ticket.scene_id == "scene_002_two_shot"
        assert ticket.severity == "blocker"
