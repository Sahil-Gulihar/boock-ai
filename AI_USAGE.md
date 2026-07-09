# AI Usage

## Tools used

Claude Code (this session, model Sonnet 5), used for the full lifecycle: brainstorming the
design, writing the implementation plan, and implementing every task test-first.

## Representative prompts/tasks

1. **"tell me how u plan to do this"** (the original assignment brief, pasted in full) —
   triggered the `superpowers:brainstorming` skill rather than jumping straight to code.
   This produced a round of clarifying questions (image track, provider, mem0 config,
   DynamoDB backend, CLI vs API scope) before any design was written down.
2. A multi-round negotiation over the image provider and memory backend: the user first
   said "OpenAI Images API," was asked to confirm a key, then said **"can u use minimax?"**
   — which required re-checking whether mem0 (chosen for durable visual memory) could
   route its internal LLM through MiniMax too. That led to an explicit lookup task rather
   than assuming: *"mem0's LLM backend list doesn't include MiniMax natively... how do you
   want to handle this?"* — user chose OpenAI-for-mem0-internals-only, MiniMax for images.
3. **"look up MiniMax's real image generation API endpoint before hardcoding request
   shape"** — used `WebSearch` + `WebFetch` against `platform.minimax.io` to get the real
   endpoint (`POST https://api.minimax.io/v1/image_generation`), auth header format, and
   request/response body shape, rather than guessing plausible-looking values. This is
   recorded verbatim in the plan's Global Constraints section and cited in `DECISIONS.md`.
4. **"write the mixed-family hard-block test first, then the node logic"** — every task in
   the implementation plan followed strict TDD: write the failing test, run it to confirm
   the expected failure mode, implement the minimal code, run again to confirm green,
   commit. This surfaced real bugs before they could compound (see #5).
5. Debugging during implementation (not scripted in the plan, discovered live): running
   `tests/test_cli.py` failed with `openai.OpenAIError: Missing credentials` even though
   the CLI only uses `MockProvider`. Root-caused to `VisualMemoryAdapter`'s default
   constructor eagerly building a real `mem0.Memory` with an OpenAI LLM config, which
   raises at *construction* time, not call time, whenever `OPENAI_API_KEY` is unset — a
   violation of the assignment's "tests must run with zero external API keys" hard rule.
6. **"run the full suite before committing each task"** — after every implementation step,
   `pytest -v` was re-run for the full suite (not just the new test file) to catch
   regressions like the `LocalArtifactStore.path_for()` bug below before they reached a
   commit.

## Where AI materially helped

- Turning an 8-hour-timeboxed, very large spec into a task-by-task TDD plan with locked
  interfaces (exact function signatures, field names) decided up front in Task 3/4/10,
  so that Tasks 11–17 never had to guess or re-derive what earlier tasks produced — this
  is what let 17 tasks ship with zero signature-mismatch bugs across the whole pipeline.
- Fetching MiniMax's actual API documentation instead of pattern-matching a "generic image
  API" shape from training data, which would likely have gotten the request body wrong
  (field names, response envelope) in a way that would only surface during a real paid-key
  smoke test, far later in the process.
- Catching and fixing two real bugs live during implementation rather than shipping a
  plan that looked correct on paper: the `mem0` OpenAI-credentials-at-construction-time
  issue (#5 above), and `LocalArtifactStore.path_for()` not creating the parent directory
  before `MockProvider.generate()` tried to `img.save()` into it (a `FileNotFoundError`
  caught by `tests/test_qa_and_repair.py`, not anticipated in the original plan).

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

Every one of the 17 implementation tasks followed the same loop: write the test, run it and
confirm the *specific* expected failure (not just "it failed"), implement, run again and
confirm green, run the *entire* suite (not just the new file), then commit. The final state
is 26 passing tests covering all 4 required categories (reference conditioning contract,
mixed-family hard block, LangGraph smoke test, DynamoDB persistence) plus 4 bonus categories
(repair tickets, FastAPI, Lambda handler, image metadata). The sample run in
`outputs/sample_run/` was generated by actually invoking `run_pipeline.py`, not
hand-written, and its `scene_lock_consistency_report.json` was spot-checked to confirm
`overall_verdict: approved` for both scenes.

## How generated code/tests were checked

Each task's diff was reviewed against the plan's locked `Interfaces` section (exact field
names and function signatures) before committing — this is why no interface drift occurred
across 17 tasks. Test code was written from the assignment's actual JSON examples (not
paraphrased), and assertions were checked against the real Pydantic model shapes rather
than assumed. No task was marked complete without its test suite actually passing in a
freshly-run `pytest -v`, shown in full in this session before each commit.
