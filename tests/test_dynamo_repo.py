import boto3
from moto import mock_aws
from src.persistence.dynamo_repo import JobRepository, TABLE_NAME


def _make_table():
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
    return dynamodb


@mock_aws
def test_job_repository_writes_and_reads_all_record_types():
    dynamodb = _make_table()
    repo = JobRepository(table_name=TABLE_NAME, dynamodb_resource=dynamodb)

    repo.create_job("job_1", "boock_demo_visual_001", "variant_cinematic_default")
    repo.record_step("job_1", "ingest_inputs", "completed", {"scenes": 2})
    repo.record_artifact("job_1", "contract", "reference_conditioning_contract", "outputs/job_1/reference_conditioning_contract.json")
    repo.record_qa_decision("job_1", "approved")
    repo.record_memory_key("job_1", "mira", 3)

    job = repo.get_job("job_1")
    assert job["meta"]["status"] == "approved"
    assert job["steps"]["ingest_inputs"]["status"] == "completed"
    assert job["artifacts"]["contract#reference_conditioning_contract"] == "outputs/job_1/reference_conditioning_contract.json"
    assert job["memory"]["mira"]["fact_count"] == 3
