import base64
from unittest.mock import MagicMock
from src.models.scene_contract import SceneRenderContract
from src.providers.minimax_provider import MiniMaxProvider


def _contract():
    return SceneRenderContract(
        scene_id="scene_001_mira_closeup", prompt="Mira under the arch", negative_prompt="anime style",
        style_route="grounded_mythic_cinematic", required_character_refs=["mira"], required_prop_refs=[],
        required_location_refs=["ruined_watchtower"], family_ids=["lockfam_character_mira_v001"],
        view_ids=["face_front_close"], provider="minimax", seed=1,
    )


def test_minimax_provider_calls_api_and_decodes_image(tmp_path):
    fake_png_b64 = base64.b64encode(b"\x89PNGfakebytes").decode()
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": {"image_base64": [fake_png_b64]}}
    mock_response.raise_for_status.return_value = None
    mock_session.post.return_value = mock_response

    provider = MiniMaxProvider(api_key="test-key", group_id="test-group", session=mock_session)
    out_path = str(tmp_path / "scene_001_mira_closeup.png")
    result = provider.generate(_contract(), {"mira": "provided_inputs/reference_assets/mira_face_ref.png"}, out_path)

    assert result.provider == "minimax"
    assert result.model == "image-01"
    posted_url = mock_session.post.call_args.args[0]
    assert posted_url == "https://api.minimax.io/v1/image_generation"
    posted_headers = mock_session.post.call_args.kwargs["headers"]
    assert posted_headers["Authorization"] == "Bearer test-key"
    with open(out_path, "rb") as f:
        assert f.read() == base64.b64decode(fake_png_b64)
