from moto import mock_aws
from src.persistence.factory import build_repo
from src.persistence.dynamo_repo import TABLE_NAME


@mock_aws
def test_build_repo_creates_table_when_missing(monkeypatch):
    monkeypatch.delenv("DYNAMODB_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    repo = build_repo()
    repo.create_job("job_1", "book_v1", "variant_v1")

    job = repo.get_job("job_1")
    assert job["meta"]["job_id"] == "job_1"


@mock_aws
def test_build_repo_is_idempotent_when_table_already_exists(monkeypatch):
    monkeypatch.delenv("DYNAMODB_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    build_repo()
    repo = build_repo()  # second call must not raise on an already-existing table
    repo.create_job("job_2", "book_v1", "variant_v1")

    job = repo.get_job("job_2")
    assert job["meta"]["job_id"] == "job_2"


@mock_aws
def test_build_repo_uses_custom_table_name(monkeypatch):
    monkeypatch.delenv("DYNAMODB_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    repo = build_repo(table_name="CustomTable")
    assert repo.table.table_name == "CustomTable"
    assert repo.table.table_name != TABLE_NAME
