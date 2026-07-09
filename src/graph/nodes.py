from __future__ import annotations
import time as _time
from src.models.state import GraphState
from src.models.inputs import ExternalReferencePack, VisualBible, ScenePacketsFile
from src.models.contracts import TypedRef, ReferenceConditioningContract
from src.models.lock_family import LockFamilyRecord, ReferenceLockFamilyManifest
from src.models.scene_contract import SceneRenderContract
from src.models.job import ImageResult, JobManifest
from src.models.qa import QACheckResult, SceneQAResult, QAReport
from src.models.repair import RepairTicket, RepairTicketManifest
from src.memory.mem0_adapter import VisualMemoryAdapter

_REQUIRED_VIEWS = {
    "character": ["face_front_close", "fullbody_front", "fullbody_three_quarter"],
    "prop": ["prop_in_hand", "prop_detail"],
}


def ingest_inputs(state: GraphState) -> GraphState:
    state.external_reference_pack = ExternalReferencePack.model_validate_json(
        open(state.external_reference_pack_path).read()
    )
    state.visual_bible = VisualBible.model_validate_json(open(state.visual_bible_path).read())
    state.scene_packets = ScenePacketsFile.model_validate_json(open(state.scene_packets_path).read())
    return state


def retrieve_visual_memory(state: GraphState, memory_adapter: VisualMemoryAdapter | None = None) -> GraphState:
    adapter = memory_adapter or VisualMemoryAdapter()
    facts: dict[str, list[str]] = {}
    for entity in state.external_reference_pack.entities:
        existing = adapter.get_facts(entity.entity_id)
        if not existing:
            for facet in entity.preserve_facets:
                adapter.save_fact(entity.entity_id, f"{entity.display_name} must preserve: {facet}")
            existing = adapter.get_facts(entity.entity_id)
        facts[entity.entity_id] = existing

    location = state.visual_bible.location
    existing_location = adapter.get_facts(location.location_id)
    if not existing_location:
        for marker in location.identity_markers:
            adapter.save_fact(location.location_id, f"{location.location_id} must preserve: {marker}")
        existing_location = adapter.get_facts(location.location_id)
    facts[location.location_id] = existing_location

    state.memory_facts = facts
    return state


def _family_id(entity_type: str, entity_id: str, reference_pack_id: str) -> str:
    return f"lockfam_{entity_type}_{entity_id}_{reference_pack_id}"


def build_reference_conditioning_contract(state: GraphState) -> GraphState:
    contract = ReferenceConditioningContract()
    reference_pack_id = state.external_reference_pack.reference_pack_id
    for entity in state.external_reference_pack.entities:
        for asset in entity.reference_assets:
            ref = TypedRef(
                entity_type=entity.entity_type,
                entity_id=entity.entity_id,
                display_name=entity.display_name,
                family_id=_family_id(entity.entity_type, entity.entity_id, reference_pack_id),
                view_id="face_front_close" if entity.entity_type == "character" else "prop_detail",
                role=asset.role,
                weight=1.0,
                preserve_facets=entity.preserve_facets,
                editable_facets=entity.editable_facets,
                approval_state="approved" if asset.required else "qa_pending",
                required=asset.required,
                source_asset_id=asset.asset_id,
                source_path=asset.path,
            )
            if asset.role == "identity_ref":
                contract.identity_refs.append(ref)
            elif asset.role == "prop_ref":
                contract.prop_refs.append(ref)
            else:
                contract.style_refs.append(ref)

    state.reference_conditioning_contract = contract
    return state


def build_reference_lock_family_manifest(state: GraphState, memory_adapter: VisualMemoryAdapter | None = None) -> GraphState:
    adapter = memory_adapter or VisualMemoryAdapter()
    reference_pack_id = state.external_reference_pack.reference_pack_id
    manifest = ReferenceLockFamilyManifest()
    for entity in state.external_reference_pack.entities:
        family_id = _family_id(entity.entity_type, entity.entity_id, reference_pack_id)
        manifest.families.append(LockFamilyRecord(
            family_id=family_id,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
            display_name=entity.display_name,
            required_views=_REQUIRED_VIEWS.get(entity.entity_type, []),
            available_views=[],
            approval_state="qa_pending",
            source_external_ref_ids=[a.asset_id for a in entity.reference_assets],
        ))
        # Durable record of "which reference-pack-derived family was approved
        # for this entity" -- lets a later run detect family drift (see
        # select_generation_strategy) if the same entity_id is later ingested
        # from a different reference pack, without needing the two refs to
        # be in the same contract at once.
        adapter.save_fact(entity.entity_id, f"approved_family_id={family_id}")
    state.lock_family_manifest = manifest
    return state


def _seed_for_scene(scene_id: str) -> int:
    return abs(hash(scene_id)) % (2 ** 31)


def _prior_approved_family_ids(entity_id: str, memory_facts: dict[str, list[str]]) -> set[str]:
    prefix = "approved_family_id="
    return {
        fact[len(prefix):] for fact in memory_facts.get(entity_id, [])
        if fact.startswith(prefix)
    }


def select_generation_strategy(state: GraphState) -> GraphState:
    contract = state.reference_conditioning_contract
    contracts: dict[str, SceneRenderContract] = {}

    for scene in state.scene_packets.scenes:
        entity_families: dict[str, set[str]] = {}
        for entity_id in list(scene.characters) + list(scene.props):
            refs = contract.refs_for_entity(entity_id)
            entity_families[entity_id] = {r.family_id for r in refs}

        block_reason = None
        block_entity_id = None

        # Same-run defense: two refs for one entity already disagree within
        # this single contract.
        for entity_id, family_ids in entity_families.items():
            if len(family_ids) > 1:
                block_reason = f"Mixed family_id refs for entity '{entity_id}': {sorted(family_ids)}"
                block_entity_id = entity_id
                break

        # Cross-run defense: this run's computed family_id for an entity
        # disagrees with a family_id previously approved (and memorized) for
        # that same entity_id -- the realistic trigger for the hard block,
        # e.g. an operator re-running the pipeline against a rotated/updated
        # reference pack for a character that was already approved before.
        if block_reason is None:
            for entity_id, family_ids in entity_families.items():
                if not family_ids:
                    continue
                current_family_id = next(iter(family_ids))
                prior_family_ids = _prior_approved_family_ids(entity_id, state.memory_facts)
                drifted = prior_family_ids - {current_family_id}
                if drifted:
                    block_reason = (
                        f"Family drift for entity '{entity_id}': previously approved "
                        f"family_id(s) {sorted(drifted)}, current run computed '{current_family_id}'"
                    )
                    block_entity_id = entity_id
                    break

        family_ids = sorted({fid for fids in entity_families.values() for fid in fids})
        view_ids = sorted({
            r.view_id for entity_id in list(scene.characters) + list(scene.props)
            for r in contract.refs_for_entity(entity_id)
        })

        contracts[scene.scene_id] = SceneRenderContract(
            scene_id=scene.scene_id,
            prompt=scene.prompt_intent,
            negative_prompt=", ".join(state.visual_bible.style.negative_style),
            style_route=state.visual_bible.style.style_route,
            required_character_refs=scene.characters,
            required_prop_refs=scene.props,
            required_location_refs=[scene.location_id],
            family_ids=family_ids,
            view_ids=view_ids,
            provider=state.provider_name,
            seed=_seed_for_scene(scene.scene_id),
            safety_notes=[],
            blocked=block_reason is not None,
            block_reason=block_reason,
            block_entity_id=block_entity_id,
        )

    state.scene_render_contracts = contracts
    return state


def render_scene_images(state: GraphState, provider, artifact_store) -> GraphState:
    images: dict[str, ImageResult] = {}
    contract = state.reference_conditioning_contract
    for scene_id, scene_contract in state.scene_render_contracts.items():
        if scene_contract.blocked:
            continue
        reference_paths = {}
        for entity_id in list(scene_contract.required_character_refs) + list(scene_contract.required_prop_refs):
            refs = contract.refs_for_entity(entity_id)
            if refs:
                reference_paths[entity_id] = refs[0].source_path
        output_path = artifact_store.path_for(f"{state.job_id}/images/{scene_id}.png")
        images[scene_id] = provider.generate(scene_contract, reference_paths, output_path)
    state.scene_images = images
    return state


def validate_scene_consistency(state: GraphState, artifact_store) -> GraphState:
    scene_results = []
    for scene_id, scene_contract in state.scene_render_contracts.items():
        checks: list[QACheckResult] = []

        if scene_contract.blocked:
            checks.append(QACheckResult(
                check_name="mixed_family_block", passed=False, severity="blocker",
                message=scene_contract.block_reason or "scene blocked",
                entity_id=scene_contract.block_entity_id,
            ))
            scene_results.append(SceneQAResult(scene_id=scene_id, checks=checks, verdict="blocked"))
            continue

        missing_characters = [
            c for c in scene_contract.required_character_refs
            if not state.reference_conditioning_contract.refs_for_entity(c)
        ]
        if missing_characters:
            for entity_id in missing_characters:
                checks.append(QACheckResult(
                    check_name="required_characters_present", passed=False, severity="blocker",
                    message=f"missing character ref for '{entity_id}'", entity_id=entity_id,
                ))
        else:
            checks.append(QACheckResult(
                check_name="required_characters_present", passed=True, severity="info",
                message="all required character refs found",
            ))

        missing_props = [
            p for p in scene_contract.required_prop_refs
            if not state.reference_conditioning_contract.refs_for_entity(p)
        ]
        if missing_props:
            for entity_id in missing_props:
                checks.append(QACheckResult(
                    check_name="required_props_present", passed=False, severity="blocker",
                    message=f"missing prop ref for '{entity_id}'", entity_id=entity_id,
                ))
        else:
            checks.append(QACheckResult(
                check_name="required_props_present", passed=True, severity="info",
                message="all required prop refs found",
            ))

        unapproved_refs = [
            e for e in (scene_contract.required_character_refs + scene_contract.required_prop_refs)
            if e not in missing_characters and e not in missing_props
            and not any(r.approval_state == "approved" for r in state.reference_conditioning_contract.refs_for_entity(e))
        ]
        if unapproved_refs:
            for entity_id in unapproved_refs:
                checks.append(QACheckResult(
                    check_name="required_refs_approved", passed=False, severity="blocker",
                    message=f"required ref for '{entity_id}' is not approved and has no explicit fallback",
                    entity_id=entity_id,
                ))
        else:
            checks.append(QACheckResult(
                check_name="required_refs_approved", passed=True, severity="info",
                message="all required refs are approved or explicitly fallback",
            ))

        image_result = state.scene_images.get(scene_id)
        image_exists = image_result is not None and image_result.width > 0 and image_result.height > 0
        checks.append(QACheckResult(
            check_name="scene_image_exists_and_valid_dimensions", passed=image_exists,
            severity="blocker" if not image_exists else "info",
            message="image rendered with valid dimensions" if image_exists else "scene image missing or invalid",
        ))

        provider_metadata_present = image_result is not None and bool(image_result.provider) and bool(image_result.model)
        checks.append(QACheckResult(
            check_name="provider_metadata_recorded", passed=provider_metadata_present,
            severity="warning" if not provider_metadata_present else "info",
            message="provider metadata present" if provider_metadata_present else "provider metadata missing",
        ))

        if any(c.severity == "blocker" and not c.passed for c in checks):
            verdict = "needs_repair"
        elif any(c.severity == "warning" and not c.passed for c in checks):
            verdict = "approved_with_warnings"
        else:
            verdict = "approved"

        scene_results.append(SceneQAResult(scene_id=scene_id, checks=checks, verdict=verdict))

    overall = "approved"
    if any(r.verdict == "blocked" for r in scene_results):
        overall = "blocked"
    elif any(r.verdict == "needs_repair" for r in scene_results):
        overall = "needs_repair"
    elif any(r.verdict == "approved_with_warnings" for r in scene_results):
        overall = "approved_with_warnings"

    state.qa_report = QAReport(job_id=state.job_id, scene_results=scene_results, overall_verdict=overall)
    artifact_store.write_json(f"{state.job_id}/scene_lock_consistency_report.json", state.qa_report.model_dump())
    return state


_RERUN_NODE_BY_CHECK = {
    "mixed_family_block": "build_reference_lock_family_manifest",
    "required_characters_present": "build_reference_conditioning_contract",
    "required_props_present": "build_reference_conditioning_contract",
    "required_refs_approved": "build_reference_conditioning_contract",
    "scene_image_exists_and_valid_dimensions": "render_scene_images",
    "provider_metadata_recorded": "render_scene_images",
}

_RECOMMENDED_ACTION_BY_CHECK = {
    "mixed_family_block": "generate_missing_lock_view",
    "required_characters_present": "generate_missing_lock_view",
    "required_props_present": "generate_missing_lock_view",
    "required_refs_approved": "approve_or_replace_reference",
    "scene_image_exists_and_valid_dimensions": "rerun_render",
    "provider_metadata_recorded": "rerun_render",
}


def decide_pass_repair_or_block(state: GraphState) -> GraphState:
    tickets: list[RepairTicket] = []
    scene_packets_by_id = {}
    if state.scene_packets is not None:
        scene_packets_by_id = {s.scene_id: s for s in state.scene_packets.scenes}

    for scene_result in state.qa_report.scene_results:
        if scene_result.verdict not in ("needs_repair", "blocked"):
            continue
        failing_checks = [c for c in scene_result.checks if not c.passed and c.severity == "blocker"]
        scene_packet = scene_packets_by_id.get(scene_result.scene_id)
        fallback_entity_id = None
        if scene_packet is not None and (scene_packet.characters or scene_packet.props):
            fallback_entity_id = (scene_packet.characters + scene_packet.props)[0]

        for failing in failing_checks:
            # Prefer the check's own typed entity_id (set precisely by
            # validate_scene_consistency/select_generation_strategy) over
            # the coarse "first entity in the scene" fallback, which is only
            # correct by coincidence for checks that don't carry one.
            entity_id = failing.entity_id or fallback_entity_id
            ticket_suffix = entity_id or "scene"
            tickets.append(RepairTicket(
                ticket_id=f"repair_{scene_result.scene_id}_{failing.check_name}_{ticket_suffix}",
                severity="blocker",
                scene_id=scene_result.scene_id,
                entity_id=entity_id,
                problem=failing.message,
                recommended_action=_RECOMMENDED_ACTION_BY_CHECK.get(failing.check_name, "rerun_render"),
                rerun_from_node=_RERUN_NODE_BY_CHECK.get(failing.check_name, "build_reference_conditioning_contract"),
            ))
    state.repair_tickets = RepairTicketManifest(tickets=tickets)
    state.job_status = state.qa_report.overall_verdict
    return state


def persist_job_state(state: GraphState, repo) -> GraphState:
    repo.create_job(state.job_id, state.book_version_id, state.variant_id)
    repo.record_step(state.job_id, "ingest_inputs", "completed", {})
    repo.record_step(state.job_id, "render_scene_images", "completed", {"scenes_rendered": len(state.scene_images)})
    repo.record_step(state.job_id, "validate_scene_consistency", "completed", {"verdict": state.qa_report.overall_verdict})
    for scene_id, image_result in state.scene_images.items():
        repo.record_artifact(state.job_id, "image", scene_id, image_result.image_path)
    repo.record_qa_decision(state.job_id, state.qa_report.overall_verdict)
    for entity_id, facts in state.memory_facts.items():
        repo.record_memory_key(state.job_id, entity_id, len(facts))
    return state


def publish_output_manifest(state: GraphState, artifact_store) -> GraphState:
    artifacts = {
        "reference_conditioning_contract": f"{state.job_id}/reference_conditioning_contract.json",
        "reference_lock_family_manifest": f"{state.job_id}/reference_lock_family_manifest.json",
        "scene_lock_consistency_report": f"{state.job_id}/scene_lock_consistency_report.json",
        "repair_ticket_manifest": f"{state.job_id}/repair_ticket_manifest.json",
    }
    for scene_id in state.scene_images:
        artifacts[f"scene_render_contract_{scene_id}"] = f"{state.job_id}/scene_render_contracts/{scene_id}.json"
        artifacts[f"image_{scene_id}"] = f"{state.job_id}/images/{scene_id}.png"

    state.job_manifest = JobManifest(
        job_id=state.job_id, book_version_id=state.book_version_id, variant_id=state.variant_id,
        status=state.job_status, created_at=str(int(_time.time())),
        artifacts=artifacts, qa_verdict=state.qa_report.overall_verdict,
    )

    artifact_store.write_json(f"{state.job_id}/reference_conditioning_contract.json", state.reference_conditioning_contract.model_dump())
    artifact_store.write_json(f"{state.job_id}/reference_lock_family_manifest.json", state.lock_family_manifest.model_dump())
    for scene_id, contract in state.scene_render_contracts.items():
        artifact_store.write_json(f"{state.job_id}/scene_render_contracts/{scene_id}.json", contract.model_dump())
    artifact_store.write_json(f"{state.job_id}/repair_ticket_manifest.json", state.repair_tickets.model_dump())
    artifact_store.write_json(f"{state.job_id}/job_manifest.json", state.job_manifest.model_dump())
    artifact_store.write_json(f"{state.job_id}/trace_report.json", {
        "job_id": state.job_id,
        "nodes_executed": [
            "ingest_inputs", "retrieve_visual_memory", "build_reference_conditioning_contract",
            "build_reference_lock_family_manifest", "select_generation_strategy", "render_scene_images",
            "validate_scene_consistency", "decide_pass_repair_or_block", "persist_job_state",
            "publish_output_manifest",
        ],
        "errors": state.errors,
        "final_status": state.job_status,
    })
    return state
