# Example Renders

Real output from this pipeline, generated end-to-end through the FastAPI server
(`POST /v1/image-consistency/render`) against the real **OpenAI `gpt-image-1`** provider,
using the reference conditioning contract built from `provided_inputs/`. Both scenes were
marked `approved` by `validate_scene_consistency` — the QA gate checks *presence* of
required refs, not visual fidelity to them, which is exactly what scene 2 below
demonstrates.

## Scene 1 — `scene_001_mira_closeup`

> Mira stands under the broken arch in rain, realizing something is wrong. Her green cloak
> and brass clasp are clearly visible.

![Mira under the arch](docs/examples/scene_001_mira_closeup_openai.png)

QA verdict: **approved**. Matches the visual bible closely — deep green hooded cloak,
brass clasp, broken stone arch, rain, dark curly hair, warm brown skin, "suspenseful,
controlled fear."

## Scene 2 — `scene_002_two_shot`

> Mira confronts Arin in the ruined watchtower. Arin hides the black seal in his hand.
> Rain reflects the blue glow on wet stone.

![Mira confronts Arin](docs/examples/scene_002_two_shot_openai.png)

QA verdict: **approved** — but this is the more interesting result. `gpt-image-1`
interpreted the prop entity `black_seal` (an obsidian, rune-engraved talisman with a thin
blue glow, per `visual_bible.json`) **literally as a baby seal animal**. Mira's cloak also
drifted from green to a blue striped sweater, and Arin's leather guard jacket became a
denim jacket with a backpack.

This is a real, useful finding, not a bug in the orchestration: `validate_scene_consistency`
currently checks that a `black_seal` reference was *resolved and passed* to the provider
(which it was — `reference_images_used` includes the prop PNG), not whether the rendered
pixels actually match what that reference depicts. A real embedding/CLIP-based similarity
check between the render and the reference image — listed under "What to productionize
next" in `DECISIONS.md` — would catch this specific failure mode and route the scene to
`needs_repair` instead of `approved`.

## Mock provider output, for comparison

`MockProvider` is what every test and the committed `outputs/sample_run/` actually run
against — deterministic placeholders, not attempts at real images:

| Scene | Mock (`outputs/sample_run/`) |
|---|---|
| `scene_001_mira_closeup` | ![mock scene 1](outputs/sample_run/images/scene_001_mira_closeup.png) |
| `scene_002_two_shot` | ![mock scene 2](outputs/sample_run/images/scene_002_two_shot.png) |

## How to reproduce

```bash
docker compose up -d   # optional, only needed for --persist / DynamoDB Local
uvicorn src.api.app:app --reload --env-file .env --port 9090
curl -s -X POST http://localhost:9090/v1/image-consistency/render \
  -H "Content-Type: application/json" \
  -d @scripts/render_request_openai.json
```

See README.md's "Chosen image provider" section for the CLI equivalent and the port-
collision note (uvicorn's default `8000` collides with DynamoDB Local's `docker-compose.yml`
port).
