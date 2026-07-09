from run_pipeline import main


def test_cli_runs_pipeline_with_mock_provider(tmp_path, capsys):
    exit_code = main([
        "--external-reference-pack", "provided_inputs/external_reference_pack.json",
        "--visual-bible", "provided_inputs/visual_bible.json",
        "--scene-packets", "provided_inputs/scene_packets.json",
        "--provider", "mock",
        "--output-dir", str(tmp_path),
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "job_id" in captured.out
    manifests = list(tmp_path.glob("*/job_manifest.json"))
    assert len(manifests) == 1
