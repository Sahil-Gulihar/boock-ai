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


def _obsidian_disc_swatch(path: Path, size: tuple[int, int], label: str) -> None:
    """Deliberately NOT face/portrait-shaped -- a round black obsidian disc
    with a thin blue glow ring and engraved rune marks, so even the
    synthetic placeholder can't be misread as a creature/animal the way a
    generic portrait ellipse could."""
    img = Image.new("RGB", size, (12, 14, 20))
    draw = ImageDraw.Draw(img)
    w, h = size

    # thin blue glow ring
    draw.ellipse([w * 0.20, h * 0.08, w * 0.80, h * 0.68], outline=(70, 160, 255), width=6)
    # black obsidian disc body
    draw.ellipse([w * 0.24, h * 0.12, w * 0.76, h * 0.64], fill=(8, 8, 10))
    # engraved rune marks (simple geometric lines, not organic/animal shapes)
    cx, cy, r = w * 0.5, h * 0.38, w * 0.16
    draw.line([cx, cy - r, cx, cy + r], fill=(70, 160, 255), width=3)
    draw.line([cx - r, cy, cx + r, cy], fill=(70, 160, 255), width=3)
    draw.ellipse([cx - r * 0.4, cy - r * 0.4, cx + r * 0.4, cy + r * 0.4], outline=(70, 160, 255), width=2)

    draw.text((10, h - 24), label, fill=(255, 255, 255))
    img.save(path)


def generate_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _labeled_swatch(out_dir / "mira_face_ref.png", (512, 512), (40, 60, 50), "MIRA_FACE_REF (synthetic)")
    _labeled_swatch(out_dir / "arin_face_ref.png", (512, 512), (35, 35, 45), "ARIN_FACE_REF (synthetic)")
    _obsidian_disc_swatch(out_dir / "black_seal_ref.png", (512, 512), "BLACK_SEAL_REF (synthetic, obsidian talisman)")


if __name__ == "__main__":
    generate_all(Path("provided_inputs/reference_assets"))
