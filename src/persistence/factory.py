from __future__ import annotations
import os
import boto3
from botocore.exceptions import ClientError
from src.persistence.dynamo_repo import JobRepository, TABLE_NAME


def _ensure_table(dynamodb_resource, table_name: str) -> None:
    try:
        table = dynamodb_resource.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceInUseException":
            raise


def build_repo(table_name: str | None = None) -> JobRepository:
    """Builds a JobRepository against either DynamoDB Local (when
    DYNAMODB_ENDPOINT_URL is set, e.g. http://localhost:8000 from
    docker-compose.yml) or real AWS DynamoDB otherwise, creating the table
    if it doesn't already exist so callers never have to provision it
    by hand first.
    """
    table_name = table_name or os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL") or None
    region = os.environ.get("AWS_REGION", "us-east-1")

    kwargs: dict = {"region_name": region}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
        # DynamoDB Local ignores credential values but boto3 still requires *some*
        # to be present when no real AWS credential chain is configured.
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "local")
        kwargs["aws_secret_access_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "local")

    dynamodb_resource = boto3.resource("dynamodb", **kwargs)
    _ensure_table(dynamodb_resource, table_name)
    return JobRepository(table_name=table_name, dynamodb_resource=dynamodb_resource)


def maybe_build_repo(explicit_persist: bool = False) -> JobRepository | None:
    """Persists to DynamoDB only when opted into, either explicitly via
    explicit_persist or implicitly because DYNAMODB_ENDPOINT_URL is set
    (e.g. the docker-compose DynamoDB Local endpoint) -- so a plain mock
    run never needs Docker or AWS running, but `docker compose up -d` plus
    a .env DYNAMODB_ENDPOINT_URL makes persistence automatic. Shared by the
    CLI, FastAPI app, and Lambda handler.
    """
    if explicit_persist or os.environ.get("DYNAMODB_ENDPOINT_URL"):
        return build_repo()
    return None
