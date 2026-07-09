from PIL import Image
from src.models.scene_contract import SceneRenderContract
from src.providers.mock_provider import MockProvider


def _contract(seed=42):
    return SceneRenderContract(
        scene_id="scene_001_mira_closeup", prompt="Mira under the arch", negative_prompt="anime style",
        style_route="grounded_mythic_cinematic", required_character_refs=["mira"], required_prop_refs=[],
        required_location_refs=["ruined_watchtower"], family_ids=["lockfam_character_mira_v001"],
        view_ids=["face_front_close"], provider="mock", seed=seed,
    )


def test_mock_provider_generates_png_with_metadata(tmp_path):
    provider = MockProvider()
    out_path = str(tmp_path / "scene_001_mira_closeup.png")
    result = provider.generate(_contract(), {"mira": "provided_inputs/reference_assets/mira_face_ref.png"}, out_path)

    assert result.provider == "mock"
    assert result.scene_id == "scene_001_mira_closeup"
    assert result.width > 0 and result.height > 0
    img = Image.open(out_path)
    assert img.size == (result.width, result.height)


def test_mock_provider_deterministic_for_same_seed(tmp_path):
    provider = MockProvider()
    p1 = str(tmp_path / "a.png")
    p2 = str(tmp_path / "b.png")
    provider.generate(_contract(seed=7), {}, p1)
    provider.generate(_contract(seed=7), {}, p2)
    assert Image.open(p1).tobytes() == Image.open(p2).tobytes()
