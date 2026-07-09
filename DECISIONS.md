# Decisions

## Why this LangGraph structure

The pipeline is a 10-node `StateGraph` (`src/graph/build_graph.py`) operating on one
Pydantic `GraphState` (`src/models/state.py`), matching the assignment's required node
list exactly: `ingest_inputs -> retrieve_visual_memory -> build_reference_conditioning_contract
-> build_reference_lock_family_manifest -> select_generation_strategy -> render_scene_images
-> validate_scene_consistency -> decide_pass_repair_or_block -> persist_job_state ->
publish_output_manifest`. Each node is a plain, independently testable function
`(GraphState, ...deps) -> GraphState` — this is why Tasks 3–12 in the implementation plan
could each ship with a focused unit test before the graph itself existed (Task 13). All
side-effecting dependencies (image provider, artifact store, DynamoDB repo, memory
adapter) are bound into node closures via `functools.partial` at `build_graph()`
construction time, so `compiled_graph.invoke(state)` is the real LangGraph dispatch path
end to end, not a manual node-by-node call chain with dependencies smuggled through
mutable state.

## Why MiniMax as the provider

User-directed choice. Isolated behind the `ImageProvider` protocol (`src/providers/base.py`)
so it's swappable — `MockProvider` is the default and the only one exercised in tests
(the assignment's hard rule: tests must never need a paid key). The MiniMax
`image_generation` endpoint shape was looked up against MiniMax's actual platform docs
(`https://platform.minimax.io/docs/guides/image-generation`) rather than guessed, to avoid
shipping a plausible-looking but wrong request format. One assumption remains unverified:
whether `subject_reference.image_file` accepts a base64 data URI for local reference images
(the documented examples show a URL) — flagged in README.md and the plan as needing a
live-key smoke test before being trusted in production.

## How character consistency is enforced

Two layers:

1. **Reference conditioning contract** (`src/graph/nodes.py::build_reference_conditioning_contract`):
   flat `external_reference_pack.json` entities become typed `TypedRef`s carrying
   `family_id`, `preserve_facets`/`editable_facets`, `approval_state`, and `source_path` —
   turning "here's a PNG" into "here's an entity-owned, versioned identity asset."
2. **Mixed-family hard block** (`select_generation_strategy`): if two refs for the same
   `entity_id` in a scene carry different `family_id` values, the scene is marked
   `blocked` *before* rendering — this is the "same character rendered from two different
   identity families looks like two different characters" failure mode the assignment
   calls out, caught structurally rather than only visually after the fact. Covered by
   `tests/test_mixed_family_block.py`, one of the four required tests.

## How memory is used

`src/memory/mem0_adapter.py::VisualMemoryAdapter` wraps mem0 behind Boock's own
`save_fact`/`get_facts` interface. `retrieve_visual_memory` seeds durable facts (e.g. "Mira
must preserve: hair_color") into mem0 on first run per entity, then reads them back on
every subsequent run — the point being that visual identity facts aren't rediscovered from
scratch each job. mem0's own LLM (used internally by mem0 for its fact
extraction/dedup step) is configured to OpenAI, not MiniMax — mem0 doesn't have a native
MiniMax LLM provider; routing it through LiteLLM's newer MiniMax support was considered and
rejected as unnecessary integration risk for a part of the assignment that's explicitly
optional-equivalent (see brainstorming transcript). If `OPENAI_API_KEY` isn't set,
`VisualMemoryAdapter` falls back automatically to `_LocalFallbackMemoryClient`, an
in-process dict-backed client with the same `add()`/`search()` shape — this was a fix made
during implementation (Task 14) after discovering mem0's OpenAI-backed LLM provider raises
at *client construction time*, not just at call time, which would otherwise have broken
the CLI/API/pytest "zero external API keys" hard rule the moment any code path exercised
the default memory adapter.

## How DynamoDB is modeled

Single table `BoockImageJobs`, PK `JOB#<job_id>`, four SK shapes (`META`,
`STEP#<node_name>`, `ARTIFACT#<type>#<id>`, `MEMORY#<entity_id>`) — one item type per
concern, queryable in one `PK`-scoped query for the whole job's history. Implemented in
`src/persistence/dynamo_repo.py`, tested against `moto` (`tests/test_dynamo_repo.py`, one
of the four required tests) so no AWS account is needed for development or CI.

## What's mocked vs real

- **Image provider**: `MockProvider` is a real, deterministic, fully-functional
  implementation (not a stub) — same seed always produces identical pixels, correct
  `ImageResult` metadata. `MiniMaxProvider` is real code calling a real (looked-up, not
  guessed) endpoint, but only exercised with a live key outside of pytest.
- **DynamoDB**: real boto3 code path, exercised against `moto`'s in-process AWS mock, not
  a live AWS account.
- **S3 storage**: real `S3ArtifactStore` code path (boto3), exercised against `moto`; the
  actual `outputs/sample_run/` artifacts were written via `LocalArtifactStore`.
- **mem0**: real SDK when `OPENAI_API_KEY` is present; falls back to an isolated in-process
  adapter with the identical interface otherwise (see above).
- **Reference images**: synthetic placeholders (see README "Known limitations"), not
  Boock-supplied.

## What to productionize next

1. **Async render queue**: move `render_scene_images` off the synchronous request path per
   `deploy_notes.md` — `POST /render` should enqueue to SQS and return `202` immediately,
   with a worker Lambda/Fargate task doing the actual render and updating DynamoDB.
2. **Real embedding-based QA checks**: add CLIP/face-embedding similarity between rendered
   scenes and reference images, prop similarity, and OCR/text-artifact detection to
   `validate_scene_consistency` — currently rule-based only (presence, mixed-family block,
   artifact/dimension validity, provider metadata).
3. **Secrets Manager** for `MINIMAX_API_KEY`/`OPENAI_API_KEY` instead of plain Lambda env
   vars.
4. **Verify MiniMax's `subject_reference` data-URI behavior** against a live account, or
   switch to pre-uploading reference images and passing URLs if data URIs aren't actually
   supported.
5. **Real Boock-supplied reference images** in place of the synthetic placeholders, and a
   corresponding lock-family QA pass that actually validates cross-view identity
   consistency rather than just presence.
6. **SAM/CDK deployment** of the Lambda + API Gateway + DynamoDB + S3 stack — `deploy_notes.md`
   documents the shape but nothing is deployed.
