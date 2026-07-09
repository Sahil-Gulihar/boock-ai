from pathlib import Path
from scripts.generate_synthetic_refs import generate_all


def test_generate_all_creates_three_pngs(tmp_path):
    out_dir = tmp_path / "reference_assets"
    generate_all(out_dir)
    assert (out_dir / "mira_face_ref.png").exists()
    assert (out_dir / "arin_face_ref.png").exists()
    assert (out_dir / "black_seal_ref.png").exists()
