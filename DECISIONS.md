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

## Why OpenAI as the provider

Started as a user-directed MiniMax choice, then switched to OpenAI `gpt-image-1` once the
user clarified that for this small system, output quality mattered more than provider
diversity. `gpt-image-1` is OpenAI's current highest-quality image model and — unlike a
plain text-to-image call — its `images.edit` endpoint accepts multiple reference images
directly, which maps naturally onto the reference-conditioning-contract design already in
place: `OpenAIImageProvider.generate()` passes the resolved character/prop reference PNGs
straight into `images.edit(image=[...], prompt=...)` when a scene has any, giving real
image-conditioned generation rather than prompt-only description. Scenes with no references
(a pure establishing shot) fall back to `images.generate(...)`. Both the endpoint shape and
the SDK method names were looked up against OpenAI's current docs
(`developers.openai.com/api/docs/guides/image-generation`) rather than guessed.

Isolated behind the same `ImageProvider` protocol (`src/providers/base.py`) as before, so
it remains swappable — `MockProvider` is still the default and the only provider exercised
in tests (the assignment's hard rule: tests must never need a paid key). Provider selection
is centralized in `src/providers/factory.py`, used identically by the CLI, FastAPI app, and
Lambda handler — previously only the CLI actually constructed the real provider object
(`_build_provider`); the API and Lambda entrypoints silently ignored the requested provider
name and always used `MockProvider`. That inconsistency was caught and fixed while making
this switch, since a "quality matters most" request loses its force if two of three
entrypoints can't actually reach the real provider.

The old `MiniMaxProvider` (and its endpoint verification) was removed rather than kept
alongside — the assignment only needs one real provider behind the interface, and keeping
a second, entirely unused real-provider implementation around would just be dead code.

## How character consistency is enforced

Three layers:

1. **Reference conditioning contract** (`src/graph/nodes.py::build_reference_conditioning_contract`):
   flat `external_reference_pack.json` entities become typed `TypedRef`s carrying
   `family_id`, `preserve_facets`/`editable_facets`, `approval_state`, and `source_path` —
   turning "here's a PNG" into "here's an entity-owned, versioned identity asset."
   `family_id` is derived from `(entity_type, entity_id, reference_pack_id)` — tying an
   entity's identity family to the specific reference pack it was approved from, not just
   a hardcoded placeholder version string (see below for why this matters).
2. **Mixed-family hard block, two triggers** (`select_generation_strategy`):
   - *Same-run*: if two refs for the same `entity_id` in one contract carry different
     `family_id` values, the scene is blocked before rendering. Covered by
     `tests/test_mixed_family_block.py`, one of the four required tests.
   - *Cross-run drift*: `build_reference_lock_family_manifest` records each entity's
     approved `family_id` as a durable mem0 fact (`approved_family_id=...`, see "How
     memory is used"). `select_generation_strategy` reads that fact back via
     `state.memory_facts` and blocks if the *current* run's computed `family_id` for an
     entity disagrees with a *previously approved* one — e.g. an operator re-running the
     pipeline against a rotated/updated reference pack for a character that was already
     approved. This is the mechanism that makes the hard block reachable through
     realistic operation rather than only through a test manually corrupting a `TypedRef`
     (an earlier version of this pipeline had exactly that gap — the block existed and
     passed its test, but `family_id` was a pure function of `(entity_type, entity_id)`
     with no version input at all, so real, unmodified data could never actually trigger
     it). Covered by `tests/test_family_drift.py`, verified against both fake memory
     clients and a live mem0/Chroma backend.
3. **`required_refs_approved` QA check** (`validate_scene_consistency`): a required
   character/prop ref existing in the contract isn't enough on its own — its
   `approval_state` must actually be `"approved"` (no unapproved-and-unfallback refs slip
   through). This is one of the assignment's eight named minimum QA checks and was
   initially missed; `approval_state` was being set on every `TypedRef` but never read
   anywhere. Covered by `tests/test_required_refs_approved_check.py`.

## How memory is used

`src/memory/mem0_adapter.py::VisualMemoryAdapter` wraps mem0 behind Boock's own
`save_fact`/`get_facts` interface. `retrieve_visual_memory` seeds durable facts (e.g. "Mira
must preserve: hair_color") into mem0 on first run per entity, then reads them back on
every subsequent run — the point being that visual identity facts aren't rediscovered from
scratch each job. It also seeds **location identity markers** (e.g. "ruined_watchtower must
preserve: broken stone arch", from `visual_bible.json`'s `location` block) the same way —
these were missing initially, even though the assignment names "ruined_watchtower identity
markers" as one of its own example facts to persist; `retrieve_visual_memory` originally only
iterated `external_reference_pack.entities` (characters/props), which never includes the
location. `build_reference_lock_family_manifest` additionally saves each entity's
**approved `family_id`** as a durable fact (`approved_family_id=...`) — also named explicitly
in the assignment's example list ("Mira approved family id") and also missing initially — this
is what the cross-run drift block (above) reads back on a later run.

mem0's own LLM (used internally by mem0 for its fact extraction/dedup step) is configured to
OpenAI's `gpt-4o-mini` — the same `OPENAI_API_KEY` now also used for the real image provider.
Every fact is saved with `infer=False`: mem0's default (`infer=True`) runs the saved text
through its own LLM and stores a *paraphrase* instead of the original string (confirmed
live: `"approved_family_id=lockfam_character_mira_refpack_demo_v001"` came back as `"User
approved the family ID 'lockfam_character_mira_refpack_demo_v001' for Mira's character."`)
— which would silently break the drift check's exact-prefix parsing against a real mem0
backend even though every test using a fake client (which stores verbatim regardless of
`infer`) passed. `infer=False` stores our already-structured fact strings verbatim, which is
also more in the spirit of mem0's stated value proposition here (reduced latency/token cost
by skipping an unnecessary LLM round-trip for text that doesn't need extraction).

If `OPENAI_API_KEY` isn't set, `VisualMemoryAdapter` falls back automatically to
`_LocalFallbackMemoryClient`, an in-process dict-backed client with the same
`add()`/`search()` shape — this was a fix made during implementation after discovering
mem0's OpenAI-backed LLM provider raises at *client construction time*, not just at call
time, which would otherwise have broken the CLI/API/pytest "zero external API keys" hard
rule the moment any code path exercised the default memory adapter. A separate fix: the
installed `mem0ai==2.0.11`'s `Memory.search()` had also drifted from the API originally
coded against — it now rejects a top-level `user_id` kwarg in favor of
`filters={"user_id": ...}` and renamed `limit` to `top_k`. Rather than push that SDK-version
churn into `VisualMemoryAdapter` or its test fakes, `_Mem0ClientShim` absorbs it, translating
Boock's stable internal call shape (`add(messages, user_id, infer)` /
`search(query, user_id, limit)`) into whatever mem0's current SDK actually wants — this is
the isolation the "clearly isolated memory adapter" requirement is for: mem0's version churn
shouldn't leak into the rest of the pipeline.

## How DynamoDB is modeled

Single table `BoockImageJobs`, PK `JOB#<job_id>`, four SK shapes (`META`,
`STEP#<node_name>`, `ARTIFACT#<type>#<id>`, `MEMORY#<entity_id>`) — one item type per
concern, queryable in one `PK`-scoped query for the whole job's history. Implemented in
`src/persistence/dynamo_repo.py`, tested against `moto` (`tests/test_dynamo_repo.py`, one
of the four required tests) so no AWS account is needed for development or CI.

Persistence is wired into all three entrypoints (CLI, FastAPI, Lambda) via
`src/persistence/factory.py::maybe_build_repo()`, but stays **off by default** — it only
activates when `DYNAMODB_ENDPOINT_URL` is set (pointing at the `docker-compose.yml`
DynamoDB Local service) or an explicit `--persist`/`"persist": true` opt-in is given. This
was a deliberate choice, not an oversight: making persistence unconditional would mean
`pytest`, the CLI's basic `--provider mock` path, and casual local runs would all suddenly
require Docker or real AWS credentials just to complete, which conflicts with "tests run
with zero external dependencies." `build_repo()` also creates the table automatically
(idempotently — `ResourceInUseException` is caught and ignored) if it doesn't already
exist, against either DynamoDB Local or real AWS, so nobody has to hand-provision it first.

**DynamoDB Local gotcha found and fixed**: the first `docker-compose.yml` pointed
`-dbPath` at a named Docker volume (`/data`) that the official `amazon/dynamodb-local`
image's non-root container user can't write to. The container reports `Up` and accepts
TCP connections, but every request just hangs forever — `docker logs` showed
`SQLiteQueue[shared-local-instance.db]: stopped abnormally, reincarnating in 3000ms` on
a loop, meaning the backing SQLite store never successfully opened. This is a genuinely
misleading failure mode: `docker ps` looks healthy, `nc -zv localhost 8000` succeeds (TCP
accepts), but any real request (e.g. `boto3`'s table-list call) blocks indefinitely with
no error. Fixed by switching to `-inMemory -sharedDb`, which needs no writable volume at
all — local dev data doesn't need to survive a container restart, so persistence-to-disk
wasn't worth the permission complexity. Verified end-to-end after the fix: a real CLI run
with `DYNAMODB_ENDPOINT_URL=http://localhost:8000` produced a fully-populated job record
in DynamoDB Local (all four SK shapes), confirmed by querying it back directly with boto3.

## What's mocked vs real

- **Image provider**: `MockProvider` is a real, deterministic, fully-functional
  implementation (not a stub) — same seed always produces identical pixels, correct
  `ImageResult` metadata. `OpenAIImageProvider` is real code calling the real, looked-up
  `gpt-image-1` SDK methods (`images.edit`/`images.generate`), but only exercised with a
  live key outside of pytest — no paid-key smoke test was run as part of this submission.
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
3. **Secrets Manager** for `OPENAI_API_KEY` instead of a plain Lambda env var.
4. **Real Boock-supplied reference images** in place of the synthetic placeholders, and a
   corresponding lock-family QA pass that actually validates cross-view identity
   consistency rather than just presence.
5. **SAM/CDK deployment** of the Lambda + API Gateway + DynamoDB + S3 stack — `deploy_notes.md`
   documents the shape but nothing is deployed.
6. **Multi-entity family drift**: `select_generation_strategy`'s drift check currently
   compares against *all* prior approved `family_id`s for an entity and blocks on any
   disagreement — it doesn't yet distinguish "this entity was legitimately re-approved
   under a new pack on purpose" from "this is an accidental regression." A real system
   would want an explicit re-approval workflow (clearing/superseding the old
   `approved_family_id` fact) rather than treating every drift as a hard error forever.

~~Run a live-key smoke test against `gpt-image-1`~~ — done: confirmed real `images.edit`
calls with reference PNGs work end-to-end via both the CLI and the FastAPI server (see
`EXAMPLES.md` for the actual generated images and a genuine consistency-drift finding from
that run).
