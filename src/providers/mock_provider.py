from __future__ import annotations
import random
import time
from PIL import Image, ImageDraw
from src.models.scene_contract import SceneRenderContract
from src.models.job import ImageResult

_WIDTH, _HEIGHT = 768, 432  # 16:9


class MockProvider:
    """Deterministic placeholder renderer: same seed -> identical pixels."""

    def generate(
        self,
        scene_contract: SceneRenderContract,
        reference_paths: dict[str, str],
        output_path: str,
    ) -> ImageResult:
        start = time.monotonic()
        rng = random.Random(scene_contract.seed)
        bg = (
            30 + rng.randint(0, 40),
            40 + rng.randint(0, 40),
            60 + rng.randint(0, 40),
        )
        img = Image.new("RGB", (_WIDTH, _HEIGHT), bg)
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, _WIDTH - 20, _HEIGHT - 20], outline=(200, 200, 200), width=2)
        draw.text((30, 30), f"MOCK RENDER: {scene_contract.scene_id}", fill=(255, 255, 255))
        draw.text((30, 55), f"characters: {','.join(scene_contract.required_character_refs)}", fill=(220, 220, 220))
        draw.text((30, 75), f"props: {','.join(scene_contract.required_prop_refs)}", fill=(220, 220, 220))
        draw.text((30, 95), f"seed: {scene_contract.seed}", fill=(220, 220, 220))
        img.save(output_path)
        runtime_ms = int((time.monotonic() - start) * 1000)

        return ImageResult(
            scene_id=scene_contract.scene_id,
            image_path=output_path,
            provider="mock",
            model="mock-render-v1",
            seed=scene_contract.seed,
            prompt=scene_contract.prompt,
            negative_prompt=scene_contract.negative_prompt,
            reference_images_used=list(reference_paths.values()),
            runtime_ms=runtime_ms,
            cost_estimate=0.0,
            width=_WIDTH,
            height=_HEIGHT,
        )
