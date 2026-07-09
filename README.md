# Boock Character-Consistent Image Pipeline

A LangGraph-orchestrated pipeline that turns a Boock story scene (character/costume/prop/
location inputs) into character-consistent scene renders, with typed reference contracts,
a reference lock-family manifest, QA/repair gating, DynamoDB persistence, and mem0-backed
durable visual memory.

**See [EXAMPLES.md](EXAMPLES.md) for real generated output** (OpenAI `gpt-image-1`),
including a genuine consistency-drift finding on scene 2 worth reading.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY if you want the real image provider
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

Pass `--provider openai` to use the real OpenAI `gpt-image-1` backend (requires
`OPENAI_API_KEY` in the environment). `outputs/sample_run/` in this repo was generated
with `--provider mock --job-id sample_run`.

FastAPI:

```bash
uvicorn src.api.app:app --reload --env-file .env
# POST http://localhost:8000/v1/image-consistency/render
# GET  http://localhost:8000/v1/image-consistency/jobs/{job_id}
```

`--env-file .env` is required — uvicorn doesn't source `.env` on its own, unlike the CLI
(which loads it automatically). **Port note:** uvicorn's default port (`8000`) collides
with DynamoDB Local's port (`docker-compose.yml`, also `8000`) if both are running — pick
one: run the API on another port (`--port 8080`) or remap DynamoDB Local's host port in
`docker-compose.yml`. If a POST to `/v1/image-consistency/render` comes back with a
`MissingAuthenticationToken` DynamoDB-shaped error, that's the tell — the request landed
on DynamoDB Local instead of the API.

## How to run tests

```bash
pytest -v
```

All 42 tests pass with **zero external API keys** — `MockProvider` is the default/only
provider exercised in tests, and `VisualMemoryAdapter` falls back to a local in-process
store when `OPENAI_API_KEY` isn't set (see DECISIONS.md).

## Chosen image provider

**OpenAI `gpt-image-1`** (`src/providers/openai_provider.py`), behind the `ImageProvider`
protocol (`src/providers/base.py`), selected via the shared `src/providers/factory.py` used
by the CLI, FastAPI app, and Lambda handler alike. Chosen over the initially-planned MiniMax
backend because output quality was the priority for this small system, and `gpt-image-1` is
OpenAI's current highest-quality image model with native multi-reference-image conditioning.

For scenes with reference images (identity/prop refs resolved from the reference
conditioning contract), it calls `client.images.edit(model="gpt-image-1", image=[...],
prompt=...)`, passing the actual reference PNGs as input files — this is real
reference-image conditioning, not just a text description of the character, which is a
better match for the assignment's character-consistency goal than a prompt-only call. Pure
location/establishing shots with no references fall back to `client.images.generate(...)`.
Both paths request `quality="high"` and `size="1536x1024"`. `OPENAI_API_KEY` is reused for
both the image provider and mem0's internal extraction step (see DECISIONS.md).

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

### Running against a real (local) DynamoDB

`docker-compose.yml` runs DynamoDB Local:

```bash
docker compose up -d
```

Persistence is **off by default** everywhere (CLI, API, Lambda) so a plain `--provider mock`
run never needs Docker or AWS running — this is what keeps `pytest` and casual runs fast
and dependency-free. It turns on automatically once `DYNAMODB_ENDPOINT_URL` is set (add it
to `.env`, or export it inline):

```bash
DYNAMODB_ENDPOINT_URL=http://localhost:8000 AWS_REGION=us-east-1 python run_pipeline.py \
  --external-reference-pack provided_inputs/external_reference_pack.json \
  --visual-bible provided_inputs/visual_bible.json \
  --scene-packets provided_inputs/scene_packets.json \
  --provider mock --output-dir outputs
```

Or force it on explicitly against real AWS with `--persist` (CLI), `"persist": true` (API
body), or `"persist": true` (Lambda event body) even without `DYNAMODB_ENDPOINT_URL` set.
`src/persistence/factory.py::build_repo()` creates the table automatically if it doesn't
already exist, against either DynamoDB Local or real AWS.

**Known DynamoDB Local gotcha** (hit and fixed during this build): the official
`amazon/dynamodb-local` image's `-dbPath` flag pointed at a Docker volume the container's
non-root user couldn't write to — the container reports `Up` and accepts TCP connections,
but every request hangs forever because its backing SQLite store never opens
(`SQLiteQueue: stopped abnormally, reincarnating in 3000ms` in `docker logs`). Fixed by
running `-inMemory` instead (see `docker-compose.yml`), which sidesteps the permission
issue entirely — local dev data doesn't need to survive a container restart anyway.

Implemented in `src/persistence/dynamo_repo.py`, tested against `moto` (no AWS account
needed) in `tests/test_dynamo_repo.py`.

## Known limitations

- **Synthetic reference images**: Boock's `provided_inputs/reference_assets/*.png` were
  not included with the assignment brief, so `scripts/generate_synthetic_refs.py` generates
  labeled placeholder PNGs in their place. Metadata/contract wiring is real; the pixel
  content is not.
- **QA checks are rule-based, not embedding-based**: `validate_scene_consistency` checks
  character/prop/location presence, reference approval state, mixed-family blocking
  (same-run and cross-run drift), artifact/dimension validity, and provider metadata — it
  does not run CLIP/face-embedding similarity, OCR, or color-palette drift checks (listed
  as bonus checks in the assignment). Documented as a productionization item in
  DECISIONS.md. `EXAMPLES.md` shows a real case (scene 2's prop drifting into a literal
  animal) that an embedding-based check would have caught and this rule-based QA cannot.
- **Family-drift detection assumes every drift is unwanted.** If an entity is legitimately
  re-approved under a new reference pack on purpose, the current design still blocks it as
  drift (no re-approval/supersede workflow exists yet — see DECISIONS.md).
- If `OPENAI_API_KEY` isn't set, `VisualMemoryAdapter` falls back automatically to a local
  in-process store so the pipeline keeps working without any keys at all.
