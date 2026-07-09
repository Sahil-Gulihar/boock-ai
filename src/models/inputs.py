from __future__ import annotations
from pydantic import BaseModel


class ReferenceAsset(BaseModel):
    asset_id: str
    path: str
    role: str
    required: bool = True


class ExternalEntity(BaseModel):
    entity_type: str  # "character" | "prop"
    entity_id: str
    display_name: str
    reference_assets: list[ReferenceAsset]
    preserve_facets: list[str]
    editable_facets: list[str]


class ExternalReferencePack(BaseModel):
    book_version_id: str
    variant_id: str
    reference_pack_id: str
    entities: list[ExternalEntity]

    def entity(self, entity_id: str) -> ExternalEntity:
        for e in self.entities:
            if e.entity_id == entity_id:
                return e
        raise KeyError(f"No entity {entity_id} in reference pack")


class VisualBibleStyle(BaseModel):
    style_route: str
    palette: list[str]
    lighting: str
    negative_style: list[str]


class VisualBibleCharacter(BaseModel):
    appearance: str
    costume: str
    must_not_change: list[str]


class VisualBibleLocation(BaseModel):
    location_id: str
    identity_markers: list[str]


class VisualBible(BaseModel):
    visual_bible_id: str
    style: VisualBibleStyle
    characters: dict[str, VisualBibleCharacter]
    location: VisualBibleLocation


class RequiredRef(BaseModel):
    entity_type: str
    entity_id: str
    view_preference: str


class ScenePacket(BaseModel):
    scene_id: str
    shot_type: str
    characters: list[str]
    props: list[str]
    location_id: str
    prompt_intent: str
    emotion: str
    required_refs: list[RequiredRef]


class ScenePacketsFile(BaseModel):
    scenes: list[ScenePacket]
