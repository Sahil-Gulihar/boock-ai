# Boock Character-Consistent Image Pipeline

A LangGraph-orchestrated pipeline that turns a Boock story scene (character/costume/prop/
location inputs) into character-consistent scene renders, with typed reference contracts,
a reference lock-family manifest, QA/repair gating, DynamoDB persistence, and mem0-backed
durable visual memory.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in MINIMAX_API_KEY / OPENAI_API_KEY if you want real providers
```

Python 3.11+ required (developed and tested on 3.14).

## How to run

CLI:

```bash
python run_pipeline.py \
  --external-reference-pack provided_inputs/external_reference_pack.json \
  --visual-bible provided_inputs/visual_bible.json \
  --scene-packets provided_inputs/scene_packets.json \
  --provider mock \
  --output-dir outputs
```

Pass `--provider minimax` to use the real MiniMax `image-01` backend (requires
`MINIMAX_API_KEY` in the environment). `outputs/sample_run/` in this repo was generated
with `--provider mock --job-id sample_run`.

FastAPI:

```bash
uvicorn src.api.app:app --reload
# POST http://localhost:8000/v1/image-consistency/render
# GET  http://localhost:8000/v1/image-consistency/jobs/{job_id}
```

## How to run tests

```bash
pytest -v
```

All 26 tests pass with **zero external API keys** — `MockProvider` is the default/only
provider exercised in tests, and `VisualMemoryAdapter` falls back to a local in-process
store when `OPENAI_API_KEY` isn't set (see DECISIONS.md).

## Chosen image provider

**MiniMax `image-01`** (`src/providers/minimax_provider.py`), behind the `ImageProvider`
protocol (`src/providers/base.py`). Endpoint: `POST https://api.minimax.io/v1/image_generation`,
verified against MiniMax's platform docs on 2026-07-09. Reference images are passed via
`subject_reference` as base64 data URIs — this specific data-URI-for-local-files behavior
is **unverified against a live account** and should be smoke-tested with a real key before
being relied on in production (see DECISIONS.md and the plan's Global Constraints).

## Mock provider behavior

`MockProvider` (`src/providers/mock_provider.py`) is the default and the only provider used
in tests/CI. It's deterministic: the same `seed` always produces byte-identical pixels. It
renders a labeled placeholder (background color derived from the seed, scene id, character
list, prop list, and seed value overlaid as text) and returns the same `ImageResult`
metadata shape (`provider`, `model`, `seed`, `prompt`, `negative_prompt`,
`reference_images_used`, `runtime_ms`, `width`, `height`) that a real provider would.

## AWS / Lambda assumptions

See `deploy_notes.md` for the full breakdown (env vars, Secrets Manager guidance, timeout
assumptions, and why a real provider render should move to an async SQS-backed queue in
production rather than run synchronously inside a Lambda). `src/lambda_handler.py` is
Lambda-ready (API-Gateway-proxy-shaped event/response) but not deployed.

## DynamoDB table design

Single table `BoockImageJobs`, on-demand billing:

| PK | SK | Purpose |
|---|---|---|
| `JOB#<job_id>` | `META` | job status, book/variant ids, created_at |
| `JOB#<job_id>` | `STEP#<node_name>` | per-node execution status/summary |
| `JOB#<job_id>` | `ARTIFACT#<type>#<id>` | artifact type/id → storage path |
| `JOB#<job_id>` | `MEMORY#<entity_id>` | fact-count recorded per entity per job |

Implemented in `src/persistence/dynamo_repo.py`, tested against `moto` (no AWS account
needed) in `tests/test_dynamo_repo.py`.

## Known limitations

- **Synthetic reference images**: Boock's `provided_inputs/reference_assets/*.png` were
  not included with the assignment brief, so `scripts/generate_synthetic_refs.py` generates
  labeled placeholder PNGs in their place. Metadata/contract wiring is real; the pixel
  content is not.
- **QA checks are rule-based, not embedding-based**: `validate_scene_consistency` checks
  presence, mixed-family blocking, artifact/dimension validity, and provider metadata —
  it does not run CLIP/face-embedding similarity, OCR, or color-palette drift checks
  (listed as bonus checks in the assignment). Documented as a productionization item in
  DECISIONS.md.
- **MiniMax `subject_reference` data-URI assumption is unverified** against a live
  MiniMax account (see above).
- **mem0's internal LLM uses OpenAI**, not MiniMax — mem0 doesn't have a native MiniMax
  LLM provider (see DECISIONS.md). If `OPENAI_API_KEY` isn't set, `VisualMemoryAdapter`
  falls back automatically to a local in-process store so the pipeline keeps working.
