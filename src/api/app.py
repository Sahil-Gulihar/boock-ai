from __future__ import annotations
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.graph.build_graph import run_job
from src.providers.factory import build_provider
from src.persistence.factory import maybe_build_repo

app = FastAPI(title="Boock Character-Consistent Image Pipeline")

_JOBS: dict[str, dict] = {}


class RenderRequest(BaseModel):
    book_version_id: str
    variant_id: str
    external_reference_pack_path: str
    visual_bible_path: str
    scene_packets_path: str
    provider: str = "mock"
    output_dir: str = "outputs"
    persist: bool = False


@app.post("/v1/image-consistency/render")
def render(req: RenderRequest):
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    state = run_job(
        job_id=job_id,
        book_version_id=req.book_version_id,
        variant_id=req.variant_id,
        external_reference_pack_path=req.external_reference_pack_path,
        visual_bible_path=req.visual_bible_path,
        scene_packets_path=req.scene_packets_path,
        provider_name=req.provider,
        output_dir=req.output_dir,
        provider=build_provider(req.provider),
        repo=maybe_build_repo(req.persist),
    )
    _JOBS[job_id] = {
        "job_id": job_id,
        "status": state.job_status,
        "qa_verdict": state.qa_report.overall_verdict if state.qa_report else None,
        "output_dir": f"{req.output_dir}/{job_id}",
    }
    return _JOBS[job_id]


@app.get("/v1/image-consistency/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in _JOBS:
        raise HTTPException(status_code=404, detail="job not found")
    return _JOBS[job_id]
