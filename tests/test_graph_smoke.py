import boto3
from moto import mock_aws
from src.persistence.dynamo_repo import JobRepository, TABLE_NAME
from src.storage.artifact_store import LocalArtifactStore
from src.providers.mock_provider import MockProvider
from src.memory.mem0_adapter import VisualMemoryAdapter
from src.graph.build_graph import run_job


class FakeMem0Client:
    def __init__(self):
        self.store = {}

    def add(self, messages, user_id, infer=True):
        self.store.setdefault(user_id, []).append(messages)

    def search(self, query, user_id, limit=10):
        return {"results": [{"memory": m} for m in self.store.get(user_id, [])]}


@mock_aws
def test_end_to_end_pipeline_with_mock_provider(tmp_path):
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    repo = JobRepository(table_name=TABLE_NAME, dynamodb_resource=dynamodb)
    store = LocalArtifactStore(base_dir=str(tmp_path))
    memory_adapter = VisualMemoryAdapter(memory_client=FakeMem0Client())

    final_state = run_job(
        job_id="job_smoke",
        book_version_id="boock_demo_visual_001",
        variant_id="variant_cinematic_default",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock",
        output_dir=str(tmp_path),
        provider=MockProvider(),
        artifact_store=store,
        repo=repo,
        memory_adapter=memory_adapter,
    )

    assert final_state.job_status in ("approved", "approved_with_warnings")
    assert set(final_state.scene_images.keys()) == {"scene_001_mira_closeup", "scene_002_two_shot"}
    assert (tmp_path / "job_smoke" / "job_manifest.json").exists()
    assert (tmp_path / "job_smoke" / "scene_lock_consistency_report.json").exists()
    assert (tmp_path / "job_smoke" / "images" / "scene_001_mira_closeup.png").exists()
    assert (tmp_path / "job_smoke" / "images" / "scene_002_two_shot.png").exists()

    persisted = repo.get_job("job_smoke")
    assert persisted["meta"]["status"] in ("approved", "approved_with_warnings")
