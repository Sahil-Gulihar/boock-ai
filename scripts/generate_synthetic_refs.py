"""Generates labeled placeholder reference images.

Boock's assignment brief references provided_inputs/reference_assets/*.png
but the actual PNG files were not included with the brief. These synthetic
images stand in for them: simple colored portraits/prop shapes with text
labels, documented as a known limitation in README.md.
"""
from pathlib import Path
from PIL import Image, ImageDraw


def _labeled_swatch(path: Path, size: tuple[int, int], bg: tuple[int, int, int], label: str) -> None:
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    draw.ellipse([size[0] * 0.25, size[1] * 0.15, size[0] * 0.75, size[1] * 0.65], fill=(220, 200, 180))
    draw.text((10, size[1] - 24), label, fill=(255, 255, 255))
    img.save(path)


def generate_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _labeled_swatch(out_dir / "mira_face_ref.png", (512, 512), (40, 60, 50), "MIRA_FACE_REF (synthetic)")
    _labeled_swatch(out_dir / "arin_face_ref.png", (512, 512), (35, 35, 45), "ARIN_FACE_REF (synthetic)")
    _labeled_swatch(out_dir / "black_seal_ref.png", (512, 512), (10, 10, 15), "BLACK_SEAL_REF (synthetic)")


if __name__ == "__main__":
    generate_all(Path("provided_inputs/reference_assets"))
