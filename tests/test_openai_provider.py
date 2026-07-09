import base64
from unittest.mock import MagicMock
from src.models.scene_contract import SceneRenderContract
from src.providers.openai_provider import OpenAIImageProvider


def _contract():
    return SceneRenderContract(
        scene_id="scene_001_mira_closeup", prompt="Mira under the arch", negative_prompt="anime style",
        style_route="grounded_mythic_cinematic", required_character_refs=["mira"], required_prop_refs=[],
        required_location_refs=["ruined_watchtower"], family_ids=["lockfam_character_mira_v001"],
        view_ids=["face_front_close"], provider="openai", seed=1,
    )


def _fake_client(fake_png_b64):
    client = MagicMock()
    response = MagicMock()
    response.data = [MagicMock(b64_json=fake_png_b64)]
    client.images.generate.return_value = response
    client.images.edit.return_value = response
    return client


def test_openai_provider_uses_edit_endpoint_when_references_present(tmp_path):
    fake_png_b64 = base64.b64encode(b"\x89PNGfakebytes").decode()
    client = _fake_client(fake_png_b64)

    provider = OpenAIImageProvider(api_key="test-key", client=client)
    out_path = str(tmp_path / "scene_001_mira_closeup.png")
    result = provider.generate(_contract(), {"mira": "provided_inputs/reference_assets/mira_face_ref.png"}, out_path)

    assert result.provider == "openai"
    assert result.model == "gpt-image-1"
    client.images.edit.assert_called_once()
    client.images.generate.assert_not_called()
    call_kwargs = client.images.edit.call_args.kwargs
    assert call_kwargs["model"] == "gpt-image-1"
    assert len(call_kwargs["image"]) == 1
    with open(out_path, "rb") as f:
        assert f.read() == base64.b64decode(fake_png_b64)


def test_openai_provider_uses_generate_endpoint_when_no_references(tmp_path):
    fake_png_b64 = base64.b64encode(b"\x89PNGfakebytes").decode()
    client = _fake_client(fake_png_b64)

    provider = OpenAIImageProvider(api_key="test-key", client=client)
    out_path = str(tmp_path / "scene_no_refs.png")
    result = provider.generate(_contract(), {}, out_path)

    client.images.generate.assert_called_once()
    client.images.edit.assert_not_called()
    assert result.provider == "openai"
