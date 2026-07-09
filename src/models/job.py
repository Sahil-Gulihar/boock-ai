from __future__ import annotations
from pydantic import BaseModel


class ImageResult(BaseModel):
    scene_id: str
    image_path: str
    provider: str
    model: str
    seed: int
    prompt: str
    negative_prompt: str
    reference_images_used: list[str]
    runtime_ms: int
    cost_estimate: float | None = None
    width: int
    height: int


class JobManifest(BaseModel):
    job_id: str
    book_version_id: str
    variant_id: str
    status: str
    created_at: str
    artifacts: dict[str, str]
    qa_verdict: str
