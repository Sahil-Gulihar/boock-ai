from __future__ import annotations
import base64
import time
import requests
from PIL import Image
from src.models.scene_contract import SceneRenderContract
from src.models.job import ImageResult

_API_URL = "https://api.minimax.io/v1/image_generation"
_MODEL = "image-01"


def _to_data_uri(image_path: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b64}"


class MiniMaxProvider:
    """Real MiniMax image-01 backend. See plan Global Constraints for the
    verified endpoint/request shape and the unverified data-URI assumption
    for subject_reference.image_file."""

    def __init__(self, api_key: str, group_id: str | None = None, session=None):
        self.api_key = api_key
        self.group_id = group_id
        self.session = session or requests

    def generate(
        self,
        scene_contract: SceneRenderContract,
        reference_paths: dict[str, str],
        output_path: str,
    ) -> ImageResult:
        start = time.monotonic()
        subject_reference = [
            {"type": "character", "image_file": _to_data_uri(path)}
            for path in reference_paths.values()
        ]
        body = {
            "model": _MODEL,
            "prompt": f"{scene_contract.prompt}. Negative: {scene_contract.negative_prompt}",
            "aspect_ratio": "16:9",
            "response_format": "base64",
        }
        if subject_reference:
            body["subject_reference"] = subject_reference

        response = self.session.post(
            _API_URL,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        image_b64 = payload["data"]["image_base64"][0]
        image_bytes = base64.b64decode(image_b64)
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        try:
            with Image.open(output_path) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0

        runtime_ms = int((time.monotonic() - start) * 1000)
        return ImageResult(
            scene_id=scene_contract.scene_id,
            image_path=output_path,
            provider="minimax",
            model=_MODEL,
            seed=scene_contract.seed,
            prompt=scene_contract.prompt,
            negative_prompt=scene_contract.negative_prompt,
            reference_images_used=list(reference_paths.values()),
            runtime_ms=runtime_ms,
            cost_estimate=None,
            width=width,
            height=height,
        )
