from __future__ import annotations
import base64
import time
from PIL import Image
from src.models.scene_contract import SceneRenderContract
from src.models.job import ImageResult

_MODEL = "gpt-image-1"
_SIZE = "1536x1024"  # closest supported landscape size to our 16:9 mock aspect ratio


class OpenAIImageProvider:
    """Real OpenAI gpt-image-1 backend.

    Uses images.edit with the character/prop reference PNGs when any are
    available for the scene -- this is what gives us actual reference-image
    conditioning for character consistency, closer to the goal than a
    prompt-only generation. Falls back to images.generate when a scene has
    no references (e.g. a pure establishing/location shot).
    """

    def __init__(self, api_key: str, client=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
        self.client = client

    def generate(
        self,
        scene_contract: SceneRenderContract,
        reference_paths: dict[str, str],
        output_path: str,
    ) -> ImageResult:
        start = time.monotonic()
        full_prompt = f"{scene_contract.prompt}. Avoid: {scene_contract.negative_prompt}"

        if reference_paths:
            image_files = [open(path, "rb") for path in reference_paths.values()]
            try:
                response = self.client.images.edit(
                    model=_MODEL,
                    image=image_files,
                    prompt=full_prompt,
                    size=_SIZE,
                    quality="high",
                )
            finally:
                for f in image_files:
                    f.close()
        else:
            response = self.client.images.generate(
                model=_MODEL,
                prompt=full_prompt,
                size=_SIZE,
                quality="high",
                n=1,
            )

        image_bytes = base64.b64decode(response.data[0].b64_json)
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
            provider="openai",
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
