from __future__ import annotations
from pydantic import BaseModel


class QACheckResult(BaseModel):
    check_name: str
    passed: bool
    severity: str  # "info" | "warning" | "blocker"
    message: str


class SceneQAResult(BaseModel):
    scene_id: str
    checks: list[QACheckResult]
    verdict: str  # "approved" | "approved_with_warnings" | "needs_repair" | "blocked"


class QAReport(BaseModel):
    job_id: str
    scene_results: list[SceneQAResult]
    overall_verdict: str
