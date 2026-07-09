from __future__ import annotations
from typing import Protocol
from src.models.scene_contract import SceneRenderContract
from src.models.job import ImageResult


class ImageProvider(Protocol):
    def generate(
        self,
        scene_contract: SceneRenderContract,
        reference_paths: dict[str, str],
        output_path: str,
    ) -> ImageResult: ...
