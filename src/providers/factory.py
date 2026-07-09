from __future__ import annotations
import os
from src.providers.mock_provider import MockProvider


def build_provider(name: str):
    """Shared provider selection used by the CLI, FastAPI app, and Lambda
    handler so all three entrypoints honor a requested real provider
    consistently, not just the CLI."""
    if name == "mock":
        return MockProvider()
    if name == "openai":
        from src.providers.openai_provider import OpenAIImageProvider
        return OpenAIImageProvider(api_key=os.environ["OPENAI_API_KEY"])
    raise ValueError(f"Unknown provider: {name}")
