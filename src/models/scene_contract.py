from __future__ import annotations
from pydantic import BaseModel


class SceneRenderContract(BaseModel):
    scene_id: str
    prompt: str
    negative_prompt: str
    style_route: str
    required_character_refs: list[str]
    required_prop_refs: list[str]
    required_location_refs: list[str]
    family_ids: list[str]
    view_ids: list[str]
    provider: str
    seed: int
    safety_notes: list[str] = []
    blocked: bool = False
    block_reason: str | None = None
