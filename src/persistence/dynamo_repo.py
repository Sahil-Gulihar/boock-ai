from __future__ import annotations
import time

TABLE_NAME = "BoockImageJobs"


class JobRepository:
    def __init__(self, table_name: str, dynamodb_resource):
        self.table = dynamodb_resource.Table(table_name)

    def create_job(self, job_id: str, book_version_id: str, variant_id: str) -> None:
        self.table.put_item(Item={
            "PK": f"JOB#{job_id}", "SK": "META",
            "job_id": job_id, "book_version_id": book_version_id, "variant_id": variant_id,
            "status": "in_progress", "created_at": str(int(time.time())),
        })

    def record_step(self, job_id: str, node_name: str, status: str, summary: dict) -> None:
        self.table.put_item(Item={
            "PK": f"JOB#{job_id}", "SK": f"STEP#{node_name}",
            "node_name": node_name, "status": status, "summary": summary,
        })

    def record_artifact(self, job_id: str, artifact_type: str, artifact_id: str, path: str) -> None:
        self.table.put_item(Item={
            "PK": f"JOB#{job_id}", "SK": f"ARTIFACT#{artifact_type}#{artifact_id}",
            "artifact_type": artifact_type, "artifact_id": artifact_id, "path": path,
        })

    def record_qa_decision(self, job_id: str, verdict: str) -> None:
        self.table.update_item(
            Key={"PK": f"JOB#{job_id}", "SK": "META"},
            UpdateExpression="SET #s = :v",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":v": verdict},
        )

    def record_memory_key(self, job_id: str, entity_id: str, fact_count: int) -> None:
        self.table.put_item(Item={
            "PK": f"JOB#{job_id}", "SK": f"MEMORY#{entity_id}",
            "entity_id": entity_id, "fact_count": fact_count,
        })

    def get_job(self, job_id: str) -> dict:
        response = self.table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"JOB#{job_id}"},
        )
        result = {"meta": {}, "steps": {}, "artifacts": {}, "memory": {}}
        for item in response["Items"]:
            sk = item["SK"]
            if sk == "META":
                result["meta"] = item
            elif sk.startswith("STEP#"):
                result["steps"][item["node_name"]] = item
            elif sk.startswith("ARTIFACT#"):
                key = f"{item['artifact_type']}#{item['artifact_id']}"
                result["artifacts"][key] = item["path"]
            elif sk.startswith("MEMORY#"):
                result["memory"][item["entity_id"]] = item
        return result
