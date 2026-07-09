from pathlib import Path
from PIL import Image
from scripts.generate_synthetic_refs import generate_all


def test_generate_all_creates_three_pngs(tmp_path):
    out_dir = tmp_path / "reference_assets"
    generate_all(out_dir)
    assert (out_dir / "mira_face_ref.png").exists()
    assert (out_dir / "arin_face_ref.png").exists()
    assert (out_dir / "black_seal_ref.png").exists()


def test_black_seal_ref_is_visually_distinct_from_the_character_portraits(tmp_path):
    """The prop placeholder must not reuse the same face-portrait ellipse
    shape as the character refs -- that shape reads as a face/head even in
    the synthetic placeholder, reinforcing the wrong idea for an object
    that's meant to be a round obsidian talisman, not a creature."""
    out_dir = tmp_path / "reference_assets"
    generate_all(out_dir)

    seal_img = Image.open(out_dir / "black_seal_ref.png").convert("RGB")
    w, h = seal_img.size
    # sampled off the rune cross-mark, within the obsidian disc body
    obsidian_pixel = seal_img.getpixel((int(w * 0.32), int(h * 0.55)))
    assert sum(obsidian_pixel) < 60

    # a blue-tinted glow ring, sampled at the ring ellipse's left edge (outside
    # the disc ellipse, which starts further right) -- blue channel clearly
    # dominant over red there
    ring_pixel = seal_img.getpixel((int(w * 0.205), int(h * 0.38)))
    assert ring_pixel[2] > ring_pixel[0] + 20
