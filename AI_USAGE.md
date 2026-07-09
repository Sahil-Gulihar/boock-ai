# AI Usage

## Tools used

Claude Code (this session, model Sonnet 5), used for the full lifecycle: brainstorming the
design, writing the implementation plan, and implementing every task test-first.

## Representative prompts/tasks

1. **Initial brainstorming.** Given the full assignment brief and asked to plan the
   approach, rather than jump straight to code — this produced a round of clarifying
   questions (image track, provider, mem0 config, DynamoDB backend, CLI vs API scope)
   before any design was written down.
2. **Provider selection.** A multi-round negotiation over the image provider and memory
   backend, ending on OpenAI for images and OpenAI-for-mem0-internals-only, which required
   explicitly checking (not assuming) whether mem0's internal LLM step could be routed
   through the other candidate provider instead.
3. **Verifying the provider API before coding against it.** Looked up the actual, current
   image-generation API docs (endpoint, auth, request/response shape) via `WebSearch`/
   `WebFetch` rather than guessing a plausible-looking request format from training data.
   Recorded verbatim in the plan and cited in `DECISIONS.md`.
4. **Strict TDD per task.** Every implementation task followed: write the failing test, run
   it to confirm the expected failure mode, implement the minimal code, run again to
   confirm green, run the full suite, commit. This is what surfaced most of the real bugs
   below before they could compound.
5. **A live bug report, not a hypothetical:** the user's `.env` file existed but its values
   weren't being picked up. Root-caused by tracing the actual failure rather than
   speculating: `python-dotenv` was a listed dependency but `load_dotenv()` was never
   called anywhere in the codebase.
6. **DynamoDB Local via Docker.** Asked one clarifying question (DynamoDB Local only vs.
   also containerizing the app) before writing anything, then verified the result
   end-to-end with real Docker commands rather than trusting `docker ps` output at face
   value — which is what caught the permission bug described below.
7. **A direct challenge to verify claims, not just re-review code.** Asked whether the
   completed code review had actually been cross-checked against the assignment text
   itself. The honest answer was no — the review had only hunted for bugs in code that
   existed, never checked for required functionality that was simply missing. Re-reading
   the assignment section-by-section against the actual repo surfaced two real gaps a
   bug-hunt alone could not have found (see "Spec cross-check" below).
8. **A terse "implement it,"** scoped entirely by the prior message's findings (the missing
   QA check, two memory gaps, and the `family_id` versioning fix). While rewriting the
   touched functions for that fix, also fixed two already-confirmed code-review findings in
   the same functions rather than leave known landmines in code already being rewritten.

## Provider switch (MiniMax -> OpenAI)

Implemented the same way as the original build: TDD per component
(`tests/test_openai_provider.py` written and run-to-fail before `src/providers/openai_provider.py`
existed), then a full-suite rerun before committing. While making the switch, discovered
and fixed a real pre-existing bug unrelated to the provider itself: only the CLI's
`_build_provider` ever constructed a real provider object — the FastAPI app and Lambda
handler both accepted a `provider` field in their request body but silently ignored it and
always ran `MockProvider`. Centralized provider selection into `src/providers/factory.py`
(with its own test, `tests/test_provider_factory.py`) so all three entrypoints are
consistent. This wasn't asked for directly, but leaving it unfixed while switching providers
for output quality would have meant two of three entrypoints still couldn't reach the new,
higher-quality provider at all.

## DynamoDB Local: a hang that looked like success

Wiring `docker-compose.yml` for DynamoDB Local and running a real end-to-end CLI test
against it surfaced two more real bugs, only found because the smoke test was actually run
rather than assumed to work from the config looking reasonable:

1. `docker ps` reported the container `Up`, and `nc -zv localhost 8000` succeeded (TCP
   accepts connections) — but every real DynamoDB request hung indefinitely. `docker logs`
   revealed the actual cause: `-dbPath /data` pointed at a Docker volume the official
   image's non-root user can't write to, so its backing SQLite store never opened
   (`SQLiteQueue: stopped abnormally, reincarnating in 3000ms`, looping silently). Neither
   `docker ps` nor a bare TCP check would ever have surfaced this — only an actual
   `boto3` call against it did. Fixed by switching to `-inMemory -sharedDb`, which needs no
   writable volume.
2. Once that was fixed and a real job ran through, `mem0ai==2.0.11`'s `Memory.search()`
   turned out to have already drifted from the API `mem0_adapter.py` was originally coded
   against (`ValueError: ... Use filters={'user_id': ...} instead`) — caught by actually
   exercising the real SDK with a real key, not just the mocked test client, which by
   construction can't detect its real counterpart's API having moved.

Both fixes were verified by re-running the real pipeline against DynamoDB Local afterward
and querying the persisted job back out directly with `boto3` to confirm all four SK shapes
(`META`, `STEP#*`, `ARTIFACT#*`, `MEMORY#*`) were actually populated correctly — not just
that the command exited 0.

## Spec cross-check: bug-hunting isn't the same as completeness-checking

A code-review pass (8 finder angles, verified findings) had already run and found 8 real
bugs — but every one of them was a bug in code that existed. Cross-checking against the
assignment text itself, a literal section-by-section pass (required JSON field lists, the 8
named minimum QA checks, the 5 named example memory facts) surfaced two things the bug hunt
structurally could not have found, because there was no code to point a finder angle at:

1. The spec lists 8 minimum QA checks; `validate_scene_consistency` only implemented 4
   distinct ones. `approval_state` was set on every `TypedRef` (`"approved"`/`"qa_pending"`)
   but never read anywhere — "required refs are approved or explicitly fallback" was a
   named requirement with zero implementation.
2. The spec's own memory example list names "Mira approved family id" and "ruined_watchtower
   identity markers" as facts to persist. `retrieve_visual_memory` only ever iterated
   `external_reference_pack.entities` (characters/props) — it never touched
   `visual_bible.json`'s `location` block, and never stored an approved `family_id` as a
   fact at all, only descriptive `preserve_facets` strings.

The bigger finding was connecting this to the earlier top code-review result: the spec's own
words are `"Hard block condition: If two refs for the same entity use different family_id
values, block the scene before rendering."` The review had already shown `_family_id()` was
a pure function of `(entity_type, entity_id)` with no version input, so that exact condition
could only ever be produced by a test manually corrupting a `TypedRef` — never by real data.
That's not a style nitpick; it's a required mechanism that only existed on paper. Fixing it
meant designing an actual reachable trigger (see DECISIONS.md's cross-run drift detection),
not just patching the test.

## Where AI materially helped

- Turning an 8-hour-timeboxed, very large spec into a task-by-task TDD plan with locked
  interfaces (exact function signatures, field names) decided up front, so later tasks
  never had to guess or re-derive what earlier tasks produced — this is what let 17 tasks
  ship with zero signature-mismatch bugs across the whole pipeline.
- Fetching the image provider's actual API documentation instead of pattern-matching a
  "generic image API" shape from training data, which would likely have gotten the request
  body wrong (field names, response envelope) in a way that would only surface during a
  real paid-key smoke test, far later in the process.
- Catching and fixing real bugs live during implementation rather than shipping a plan that
  looked correct on paper: `VisualMemoryAdapter`'s default constructor eagerly building a
  real `mem0.Memory` that raised at construction time (not call time) whenever
  `OPENAI_API_KEY` was unset, violating the "tests run with zero external API keys" rule;
  and `LocalArtifactStore.path_for()` not creating the parent directory before
  `MockProvider.generate()` tried to `img.save()` into it.

## One AI suggestion rejected/corrected

The original plan's `decide_pass_repair_or_block` unconditionally iterated
`state.scene_packets.scenes` to look up an entity id for a repair ticket. While
implementing `tests/test_qa_and_repair.py` (whose fixture deliberately doesn't call
`ingest_inputs`, to keep the QA-node tests focused on QA logic rather than full ingestion),
this would have crashed with `AttributeError: 'NoneType' object has no attribute 'scenes'`.
Rather than patching the test to work around it, the node itself was corrected to guard for
`state.scene_packets is None` — the more defensible fix, since a QA/repair node shouldn't
assume every caller ran the full pipeline up to that point.

## How correctness was verified

Every implementation task followed the same loop: write the test, run it and confirm the
*specific* expected failure (not just "it failed"), implement, run again and confirm green,
run the *entire* suite (not just the new file), then commit. The final state is 42 passing
tests covering all 4 required categories (reference conditioning contract, mixed-family
hard block, LangGraph smoke test, DynamoDB persistence) plus bonus categories (repair
tickets, FastAPI, Lambda handler, image metadata, OpenAI provider, provider factory,
persistence factory, family drift, memory coverage). The sample run in
`outputs/sample_run/` was generated by actually invoking `run_pipeline.py`, not
hand-written, and its `scene_lock_consistency_report.json` was spot-checked after every
significant change to confirm `overall_verdict: approved` for both scenes.

For the family-drift fix specifically, passing tests weren't treated as sufficient on their
own, because the tests use fake memory clients that store facts verbatim — exactly the kind
of test that can hide a bug that only shows up against the real dependency. The fix was also
verified against the actual live mem0/Chroma backend (real `OPENAI_API_KEY`, persisted
`chroma_db/`): first confirming the newly-saved `approved_family_id=...` fact came back
through `get_facts()` as a *paraphrase* rather than the original string (mem0's `infer=True`
default silently rewrites saved text through its own LLM), which would have made the drift
check's exact-string parsing never match anything in production despite every test passing —
then fixing it (`infer=False`) and re-confirming verbatim storage, then actually triggering a
real drift block end-to-end against the live backend (a second "run" with a rotated
`reference_pack_id`, no test doubles involved) and reading back `scene.blocked == True` with
the correct entity and reason. This caught a bug that would have shipped invisibly: 42/42
tests green, and the flagship fix silently inert in production.

## How generated code/tests were checked

Each task's diff was reviewed against the plan's locked interfaces (exact field names and
function signatures) before committing — this is why no interface drift occurred across the
build. Test code was written from the assignment's actual JSON examples (not paraphrased),
and assertions were checked against the real Pydantic model shapes rather than assumed. No
task was marked complete without its test suite actually passing in a freshly-run
`pytest -v`, shown in full before each commit.
