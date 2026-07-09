import json
from src.lambda_handler import lambda_handler


def test_lambda_handler_runs_pipeline_from_api_gateway_event(tmp_path):
    event = {
        "body": json.dumps({
            "book_version_id": "boock_demo_visual_001",
            "variant_id": "variant_cinematic_default",
            "external_reference_pack_path": "provided_inputs/external_reference_pack.json",
            "visual_bible_path": "provided_inputs/visual_bible.json",
            "scene_packets_path": "provided_inputs/scene_packets.json",
            "provider": "mock",
            "output_dir": str(tmp_path),
        })
    }
    response = lambda_handler(event, context=None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] in ("approved", "approved_with_warnings")
