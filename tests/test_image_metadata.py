from src.models.state import GraphState
from src.models.contracts import ReferenceConditioningContract
from src.models.scene_contract import SceneRenderContract
from src.storage.artifact_store import LocalArtifactStore
from src.providers.mock_provider import MockProvider
from src.graph.nodes import render_scene_images


def test_rendered_image_result_has_full_provider_metadata(tmp_path):
    state = GraphState(
        job_id="job_meta", book_version_id="b", variant_id="v",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir=str(tmp_path),
    )
    state.reference_conditioning_contract = ReferenceConditioningContract()
    state.scene_render_contracts = {
        "scene_meta": SceneRenderContract(
            scene_id="scene_meta", prompt="p", negative_prompt="n", style_route="grounded_mythic_cinematic",
            required_character_refs=[], required_prop_refs=[], required_location_refs=["ruined_watchtower"],
            family_ids=[], view_ids=[], provider="mock", seed=5,
        )
    }
    state = render_scene_images(state, provider=MockProvider(), artifact_store=LocalArtifactStore(base_dir=str(tmp_path)))
    result = state.scene_images["scene_meta"]
    for field in ("provider", "model", "prompt", "negative_prompt", "runtime_ms", "width", "height"):
        assert getattr(result, field) not in (None, "")
    assert result.width > 0 and result.height > 0
