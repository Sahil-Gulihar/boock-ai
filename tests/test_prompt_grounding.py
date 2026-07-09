from src.models.state import GraphState
from src.graph.nodes import (
    ingest_inputs, build_reference_conditioning_contract, select_generation_strategy,
)


def _base_state():
    return GraphState(
        job_id="job_grounding", book_version_id="boock_demo_visual_001", variant_id="variant_cinematic_default",
        external_reference_pack_path="provided_inputs/external_reference_pack.json",
        visual_bible_path="provided_inputs/visual_bible.json",
        scene_packets_path="provided_inputs/scene_packets.json",
        provider_name="mock", output_dir="outputs",
    )


def test_prop_prompt_disambiguates_against_literal_name_reading():
    """A prop entity_id like 'black_seal' is easy for an image model to
    misread as the animal. The prompt sent to the provider must carry the
    reference conditioning contract's own preserve_facets so the provider
    knows it's an inanimate object, not just the scene's freeform text."""
    state = ingest_inputs(_base_state())
    state = build_reference_conditioning_contract(state)
    state = select_generation_strategy(state)

    scene_002 = state.scene_render_contracts["scene_002_two_shot"]
    prompt_lower = scene_002.prompt.lower()

    assert "black obsidian" in prompt_lower or "obsidian" in prompt_lower
    assert "not an animal" in prompt_lower or "inanimate" in prompt_lower
    assert "engraved rune" in prompt_lower or "rune" in prompt_lower


def test_character_prompt_includes_preserve_facets():
    state = ingest_inputs(_base_state())
    state = build_reference_conditioning_contract(state)
    state = select_generation_strategy(state)

    scene_001 = state.scene_render_contracts["scene_001_mira_closeup"]
    prompt_lower = scene_001.prompt.lower()

    assert "hair_color" in prompt_lower or "hair color" in prompt_lower
    assert "mira" in prompt_lower


def test_original_prompt_intent_is_preserved_as_a_prefix():
    state = ingest_inputs(_base_state())
    state = build_reference_conditioning_contract(state)
    state = select_generation_strategy(state)

    scene_001 = state.scene_render_contracts["scene_001_mira_closeup"]
    original = state.scene_packets.scenes[0].prompt_intent
    assert scene_001.prompt.startswith(original)
