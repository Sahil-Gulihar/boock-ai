from pathlib import Path
from src.models.inputs import ExternalReferencePack, VisualBible, ScenePacketsFile


def test_parses_provided_inputs():
    pack = ExternalReferencePack.model_validate_json(
        Path("provided_inputs/external_reference_pack.json").read_text()
    )
    assert pack.book_version_id == "boock_demo_visual_001"
    assert {e.entity_id for e in pack.entities} == {"mira", "arin", "black_seal"}

    bible = VisualBible.model_validate_json(Path("provided_inputs/visual_bible.json").read_text())
    assert bible.location.location_id == "ruined_watchtower"

    scenes = ScenePacketsFile.model_validate_json(Path("provided_inputs/scene_packets.json").read_text())
    assert len(scenes.scenes) == 2
    assert scenes.scenes[1].props == ["black_seal"]
