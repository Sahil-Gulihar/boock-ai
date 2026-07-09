from src.models.contracts import TypedRef, ReferenceConditioningContract
from src.models.lock_family import LockFamilyRecord, ReferenceLockFamilyManifest
from src.models.scene_contract import SceneRenderContract
from src.models.qa import QACheckResult, SceneQAResult, QAReport
from src.models.repair import RepairTicket, RepairTicketManifest
from src.models.job import ImageResult, JobManifest


def test_reference_conditioning_contract_round_trip():
    ref = TypedRef(
        entity_type="character", entity_id="mira", display_name="Mira",
        family_id="lockfam_character_mira_v001", view_id="face_front_close",
        role="identity_ref", weight=1.0, preserve_facets=["face_identity"],
        editable_facets=["pose"], approval_state="approved", required=True,
        source_asset_id="mira_face_ref", source_path="provided_inputs/reference_assets/mira_face_ref.png",
    )
    contract = ReferenceConditioningContract(identity_refs=[ref])
    data = contract.model_dump_json()
    assert ReferenceConditioningContract.model_validate_json(data) == contract


def test_scene_render_contract_defaults_not_blocked():
    contract = SceneRenderContract(
        scene_id="scene_001", prompt="p", negative_prompt="n", style_route="grounded_mythic_cinematic",
        required_character_refs=["mira"], required_prop_refs=[], required_location_refs=["ruined_watchtower"],
        family_ids=["lockfam_character_mira_v001"], view_ids=["face_front_close"], provider="mock", seed=1,
        safety_notes=[],
    )
    assert contract.blocked is False
    assert contract.block_reason is None


def test_qa_report_and_repair_ticket_shapes():
    check = QACheckResult(check_name="characters_present", passed=True, severity="info", message="ok")
    scene_result = SceneQAResult(scene_id="scene_001", checks=[check], verdict="approved")
    report = QAReport(job_id="job_1", scene_results=[scene_result], overall_verdict="approved")
    assert report.overall_verdict == "approved"

    ticket = RepairTicket(
        ticket_id="repair_scene_002_mira_identity", severity="blocker", scene_id="scene_002_two_shot",
        entity_id="mira", problem="missing view", recommended_action="generate_missing_lock_view",
        rerun_from_node="build_reference_lock_family_manifest",
    )
    manifest = RepairTicketManifest(tickets=[ticket])
    assert manifest.tickets[0].severity == "blocker"
