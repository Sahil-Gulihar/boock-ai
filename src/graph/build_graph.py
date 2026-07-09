from __future__ import annotations
from functools import partial
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.models.state import GraphState
from src.storage.artifact_store import LocalArtifactStore
from src.providers.mock_provider import MockProvider
from src.memory.mem0_adapter import VisualMemoryAdapter
from src.graph import nodes as N


def build_graph(provider=None, artifact_store=None, repo=None, memory_adapter=None):
    """Compiles the LangGraph StateGraph, binding side-effecting dependencies
    (provider/artifact_store/repo/memory_adapter) into each node via
    functools.partial closures so graph.invoke(state) alone drives execution
    -- no dependency-smuggling through mutable state needed."""
    provider = provider or MockProvider()
    artifact_store = artifact_store or LocalArtifactStore(base_dir="outputs")
    memory_adapter = memory_adapter or VisualMemoryAdapter()

    graph = StateGraph(GraphState)
    graph.add_node("ingest_inputs", N.ingest_inputs)
    graph.add_node("retrieve_visual_memory", partial(N.retrieve_visual_memory, memory_adapter=memory_adapter))
    graph.add_node("build_reference_conditioning_contract", N.build_reference_conditioning_contract)
    graph.add_node("build_reference_lock_family_manifest", partial(N.build_reference_lock_family_manifest, memory_adapter=memory_adapter))
    graph.add_node("select_generation_strategy", N.select_generation_strategy)
    graph.add_node("render_scene_images", partial(N.render_scene_images, provider=provider, artifact_store=artifact_store))
    graph.add_node("validate_scene_consistency", partial(N.validate_scene_consistency, artifact_store=artifact_store))
    graph.add_node("decide_pass_repair_or_block", N.decide_pass_repair_or_block)
    if repo is not None:
        graph.add_node("persist_job_state", partial(N.persist_job_state, repo=repo))
    else:
        graph.add_node("persist_job_state", lambda s: s)
    graph.add_node("publish_output_manifest", partial(N.publish_output_manifest, artifact_store=artifact_store))

    graph.set_entry_point("ingest_inputs")
    graph.add_edge("ingest_inputs", "retrieve_visual_memory")
    graph.add_edge("retrieve_visual_memory", "build_reference_conditioning_contract")
    graph.add_edge("build_reference_conditioning_contract", "build_reference_lock_family_manifest")
    graph.add_edge("build_reference_lock_family_manifest", "select_generation_strategy")
    graph.add_edge("select_generation_strategy", "render_scene_images")
    graph.add_edge("render_scene_images", "validate_scene_consistency")
    graph.add_edge("validate_scene_consistency", "decide_pass_repair_or_block")
    graph.add_edge("decide_pass_repair_or_block", "persist_job_state")
    graph.add_edge("persist_job_state", "publish_output_manifest")
    graph.add_edge("publish_output_manifest", END)

    return graph.compile(checkpointer=MemorySaver())


def run_job(
    job_id: str,
    book_version_id: str,
    variant_id: str,
    external_reference_pack_path: str,
    visual_bible_path: str,
    scene_packets_path: str,
    provider_name: str = "mock",
    output_dir: str = "outputs",
    provider=None,
    artifact_store=None,
    repo=None,
    memory_adapter=None,
) -> GraphState:
    artifact_store = artifact_store or LocalArtifactStore(base_dir=output_dir)
    provider = provider or MockProvider()
    memory_adapter = memory_adapter or VisualMemoryAdapter()

    compiled_graph = build_graph(
        provider=provider, artifact_store=artifact_store, repo=repo, memory_adapter=memory_adapter,
    )

    initial_state = GraphState(
        job_id=job_id, book_version_id=book_version_id, variant_id=variant_id,
        external_reference_pack_path=external_reference_pack_path,
        visual_bible_path=visual_bible_path, scene_packets_path=scene_packets_path,
        provider_name=provider_name, output_dir=output_dir,
    )

    result = compiled_graph.invoke(
        initial_state, config={"configurable": {"thread_id": job_id}},
    )
    return GraphState.model_validate(result)
