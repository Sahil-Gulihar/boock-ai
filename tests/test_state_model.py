from src.models.state import GraphState


def test_graph_state_constructs_with_minimal_fields():
    state = GraphState(
        job_id="job_1",
        book_version_id="boock_demo_visual_001",
        variant_id="variant_cinematic_default",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock",
        output_dir="outputs",
    )
    assert state.job_id == "job_1"
    assert state.scene_render_contracts == {}
    assert state.errors == []
