from __future__ import annotations
from pydantic import BaseModel


class LockFamilyRecord(BaseModel):
    family_id: str
    entity_type: str
    entity_id: str
    display_name: str
    required_views: list[str]
    available_views: list[str] = []
    approval_state: str = "qa_pending"
    source_external_ref_ids: list[str]


class ReferenceLockFamilyManifest(BaseModel):
    families: list[LockFamilyRecord] = []

    def family_for_entity(self, entity_id: str) -> LockFamilyRecord | None:
        for f in self.families:
            if f.entity_id == entity_id:
                return f
        return None
