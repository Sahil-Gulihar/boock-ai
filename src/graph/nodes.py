from __future__ import annotations
from src.models.state import GraphState
from src.models.inputs import ExternalReferencePack, VisualBible, ScenePacketsFile
from src.models.contracts import TypedRef, ReferenceConditioningContract
from src.models.lock_family import LockFamilyRecord, ReferenceLockFamilyManifest
from src.models.scene_contract import SceneRenderContract
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
    state.memory_facts = facts
    return state


def _family_id(entity_type: str, entity_id: str) -> str:
    return f"lockfam_{entity_type}_{entity_id}_v001"


def build_reference_conditioning_contract(state: GraphState) -> GraphState:
    contract = ReferenceConditioningContract()
    for entity in state.external_reference_pack.entities:
        for asset in entity.reference_assets:
            ref = TypedRef(
                entity_type=entity.entity_type,
                entity_id=entity.entity_id,
                display_name=entity.display_name,
                family_id=_family_id(entity.entity_type, entity.entity_id),
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


def build_reference_lock_family_manifest(state: GraphState) -> GraphState:
    manifest = ReferenceLockFamilyManifest()
    for entity in state.external_reference_pack.entities:
        manifest.families.append(LockFamilyRecord(
            family_id=_family_id(entity.entity_type, entity.entity_id),
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
            display_name=entity.display_name,
            required_views=_REQUIRED_VIEWS.get(entity.entity_type, []),
            available_views=[],
            approval_state="qa_pending",
            source_external_ref_ids=[a.asset_id for a in entity.reference_assets],
        ))
    state.lock_family_manifest = manifest
    return state


def _seed_for_scene(scene_id: str) -> int:
    return abs(hash(scene_id)) % (2 ** 31)


def select_generation_strategy(state: GraphState) -> GraphState:
    contract = state.reference_conditioning_contract
    contracts: dict[str, SceneRenderContract] = {}

    for scene in state.scene_packets.scenes:
        character_families: dict[str, set[str]] = {}
        for entity_id in scene.characters:
            refs = contract.refs_for_entity(entity_id)
            character_families[entity_id] = {r.family_id for r in refs}
        for prop_id in scene.props:
            refs = contract.refs_for_entity(prop_id)
            character_families[prop_id] = {r.family_id for r in refs}

        block_reason = None
        for entity_id, family_ids in character_families.items():
            if len(family_ids) > 1:
                block_reason = f"Mixed family_id refs for entity '{entity_id}': {sorted(family_ids)}"
                break

        family_ids = sorted({fid for fids in character_families.values() for fid in fids})
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
        )

    state.scene_render_contracts = contracts
    return state
