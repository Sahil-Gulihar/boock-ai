from fastapi.testclient import TestClient
from src.api.app import app


def test_render_endpoint_runs_pipeline_and_get_endpoint_returns_it():
    client = TestClient(app)
    response = client.post("/v1/image-consistency/render", json={
        "book_version_id": "boock_demo_visual_001",
        "variant_id": "variant_cinematic_default",
        "external_reference_pack_path": "provided_inputs/external_reference_pack.json",
        "visual_bible_path": "provided_inputs/visual_bible.json",
        "scene_packets_path": "provided_inputs/scene_packets.json",
        "provider": "mock",
        "output_dir": "outputs",
    })
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert response.json()["status"] in ("approved", "approved_with_warnings")

    get_response = client.get(f"/v1/image-consistency/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["job_id"] == job_id


def test_get_unknown_job_returns_404():
    client = TestClient(app)
    response = client.get("/v1/image-consistency/jobs/does_not_exist")
    assert response.status_code == 404
