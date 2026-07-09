import boto3
from moto import mock_aws
from src.storage.artifact_store import LocalArtifactStore, S3ArtifactStore


def test_local_artifact_store_write_read_json(tmp_path):
    store = LocalArtifactStore(base_dir=str(tmp_path))
    path = store.write_json("job_1/reference_conditioning_contract.json", {"a": 1})
    assert path == str(tmp_path / "job_1/reference_conditioning_contract.json")
    assert store.read_json("job_1/reference_conditioning_contract.json") == {"a": 1}


def test_local_artifact_store_write_bytes(tmp_path):
    store = LocalArtifactStore(base_dir=str(tmp_path))
    path = store.write_bytes("job_1/images/scene_001.png", b"fakepng")
    assert (tmp_path / "job_1/images/scene_001.png").read_bytes() == b"fakepng"
    assert path.endswith("scene_001.png")


@mock_aws
def test_s3_artifact_store_write_read_json():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")
    store = S3ArtifactStore(bucket="test-bucket", s3_client=s3)
    store.write_json("job_1/job_manifest.json", {"status": "approved"})
    assert store.read_json("job_1/job_manifest.json") == {"status": "approved"}
