# Deploy Notes (Lambda-readiness, not deployed)

## Environment variables
- `OPENAI_API_KEY` — used for both the real image provider (`gpt-image-1`) and internally
  by mem0's fact-extraction step. **Do not set as a plain Lambda env var in production** —
  AWS recommends Secrets Manager for sensitive values; fetch at cold-start and cache in the
  execution environment instead. If unset, `VisualMemoryAdapter` falls back automatically
  to a local in-process memory store (see DECISIONS.md) rather than failing, but
  `--provider openai` / `"provider": "openai"` will raise since the image provider has no
  fallback path.
- `DYNAMODB_TABLE_NAME` — defaults to `BoockImageJobs`.
- `ARTIFACT_BUCKET_NAME` — S3 bucket for `S3ArtifactStore` in place of `LocalArtifactStore`.
- `AWS_REGION` — region for DynamoDB/S3 clients.

## DynamoDB table
Table `BoockImageJobs`, on-demand billing, PK `PK` (string), SK `SK` (string). See
README.md "DynamoDB table design" for the full key scheme.

## Artifact bucket
S3 bucket holding the same key layout as `outputs/<job_id>/...` locally
(`reference_conditioning_contract.json`, `images/<scene_id>.png`, etc).

## Provider API key handling
Local/dev: `.env` file (gitignored), loaded via `python-dotenv`. Production: Secrets
Manager, resolved at Lambda cold start, never baked into the deployment package or
container image.

## Local mock mode
`--provider mock` (CLI) or `"provider": "mock"` (API/Lambda body) uses `MockProvider` —
no network calls, no external credentials, deterministic output. This is also what every
`pytest` run uses.

## Timeout assumptions
API Gateway + Lambda proxy integration has a 29s/15min hard ceiling. `MockProvider` runs
in milliseconds, well within any Lambda timeout. A real provider call plus multi-scene
rendering could approach or exceed the 15-minute Lambda ceiling for larger jobs.

## Why long-running GPU render should move to async queue in production
Image generation (especially provider-hosted GPU models) is latency-variable and can be
rate-limited or slow (seconds to minutes per image, worse under provider load). Running it
synchronously inside a request-response Lambda risks API Gateway/Lambda timeouts and wastes
Lambda billed duration waiting on an external call. Production shape: `POST /render` enqueues
a job (SQS) and returns `202 Accepted` + `job_id` immediately; a separate worker (Lambda with
a longer configured timeout, or a Fargate task for genuinely long GPU jobs) consumes the
queue, runs `run_job`, and updates DynamoDB job status; `GET /jobs/{job_id}` polls DynamoDB
for status/artifacts. This assignment's synchronous Lambda handler is intentionally the
simple/demo shape, not the production shape — documented here and in DECISIONS.md.

## Container-image deployment path
`src/lambda_handler.py` has no filesystem assumptions beyond writable `/tmp`, so it's
compatible with either zip-based Lambda packaging or an ECR container image (needed once
Track A dependencies like Pillow's compiled wheels, chromadb, or mem0's vector store grow
past the zip package size limit — likely, given chromadb's native dependencies).
