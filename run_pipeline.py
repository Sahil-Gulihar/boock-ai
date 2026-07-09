from __future__ import annotations
import argparse
import json
import uuid
from src.graph.build_graph import run_job
from src.providers.factory import build_provider
from src.persistence.factory import maybe_build_repo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Boock character-consistent image pipeline")
    parser.add_argument("--external-reference-pack", required=True)
    parser.add_argument("--visual-bible", required=True)
    parser.add_argument("--scene-packets", required=True)
    parser.add_argument("--provider", default="mock", choices=["mock", "openai"])
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--persist", action="store_true", help="Persist job state to DynamoDB (auto-enabled if DYNAMODB_ENDPOINT_URL is set)")
    args = parser.parse_args(argv)

    job_id = args.job_id or f"job_{uuid.uuid4().hex[:8]}"
    state = run_job(
        job_id=job_id,
        book_version_id="boock_demo_visual_001",
        variant_id="variant_cinematic_default",
        external_reference_pack_path=args.external_reference_pack,
        visual_bible_path=args.visual_bible,
        scene_packets_path=args.scene_packets,
        provider_name=args.provider,
        output_dir=args.output_dir,
        provider=build_provider(args.provider),
        repo=maybe_build_repo(args.persist),
    )

    print(json.dumps({"job_id": job_id, "status": state.job_status, "output_dir": f"{args.output_dir}/{job_id}"}))
    return 0


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    raise SystemExit(main())
