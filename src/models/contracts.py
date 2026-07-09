from __future__ import annotations
from pydantic import BaseModel


class TypedRef(BaseModel):
    entity_type: str
    entity_id: str
    display_name: str
    family_id: str
    view_id: str
    role: str
    weight: float
    preserve_facets: list[str]
    editable_facets: list[str]
    approval_state: str
    required: bool
    source_asset_id: str
    source_path: str


class ReferenceConditioningContract(BaseModel):
    identity_refs: list[TypedRef] = []
    structure_refs: list[TypedRef] = []
    style_refs: list[TypedRef] = []
    location_refs: list[TypedRef] = []
    prop_refs: list[TypedRef] = []
    outfit_refs: list[TypedRef] = []
    negative_entity_refs: list[TypedRef] = []

    def refs_for_entity(self, entity_id: str) -> list[TypedRef]:
        all_refs = (
            self.identity_refs + self.structure_refs + self.style_refs
            + self.location_refs + self.prop_refs + self.outfit_refs
        )
        return [r for r in all_refs if r.entity_id == entity_id]
