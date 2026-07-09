from __future__ import annotations
import json
import uuid
from src.graph.build_graph import run_job
from src.providers.factory import build_provider
from src.persistence.factory import maybe_build_repo


def lambda_handler(event, context):
    """API-Gateway-proxy-shaped Lambda entrypoint for POST /v1/image-consistency/render.

    Production note: this synchronous handler is fine for the mock provider
    (sub-second) but a real GPU/hosted-model render should be dispatched to
    an async queue (SQS + a longer-running worker Lambda or Fargate task)
    rather than run inline, since Lambda has a hard 15-minute timeout and
    image generation APIs can be slow/rate-limited. See deploy_notes.md.
    """
    body = json.loads(event.get("body") or "{}")
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    state = run_job(
        job_id=job_id,
        book_version_id=body["book_version_id"],
        variant_id=body["variant_id"],
        external_reference_pack_path=body["external_reference_pack_path"],
        visual_bible_path=body["visual_bible_path"],
        scene_packets_path=body["scene_packets_path"],
        provider_name=body.get("provider", "mock"),
        output_dir=body.get("output_dir", "/tmp/outputs"),
        provider=build_provider(body.get("provider", "mock")),
        repo=maybe_build_repo(body.get("persist", False)),
    )
    return {
        "statusCode": 200,
        "body": json.dumps({"job_id": job_id, "status": state.job_status}),
    }
