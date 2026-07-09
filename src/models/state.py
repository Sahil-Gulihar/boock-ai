from __future__ import annotations
from pydantic import BaseModel
from src.models.inputs import ExternalReferencePack, VisualBible, ScenePacketsFile
from src.models.contracts import ReferenceConditioningContract
from src.models.lock_family import ReferenceLockFamilyManifest
from src.models.scene_contract import SceneRenderContract
from src.models.job import ImageResult, JobManifest
from src.models.qa import QAReport
from src.models.repair import RepairTicketManifest


class GraphState(BaseModel):
    # inputs
    job_id: str
    book_version_id: str
    variant_id: str
    external_reference_pack_path: str
    visual_bible_path: str
    scene_packets_path: str
    provider_name: str = "mock"
    output_dir: str = "outputs"

    # loaded artifacts
    external_reference_pack: ExternalReferencePack | None = None
    visual_bible: VisualBible | None = None
    scene_packets: ScenePacketsFile | None = None

    # memory
    memory_facts: dict[str, list[str]] = {}

    # built contracts
    reference_conditioning_contract: ReferenceConditioningContract | None = None
    lock_family_manifest: ReferenceLockFamilyManifest | None = None
    scene_render_contracts: dict[str, SceneRenderContract] = {}

    # render outputs
    scene_images: dict[str, ImageResult] = {}

    # QA / repair
    qa_report: QAReport | None = None
    repair_tickets: RepairTicketManifest | None = None

    # final
    job_manifest: JobManifest | None = None
    job_status: str = "in_progress"
    errors: list[str] = []
