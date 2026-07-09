import pytest
from src.providers.factory import build_provider
from src.providers.mock_provider import MockProvider


def test_build_provider_mock_returns_mock_provider():
    assert isinstance(build_provider("mock"), MockProvider)


def test_build_provider_unknown_raises():
    with pytest.raises(ValueError):
        build_provider("not_a_real_provider")


def test_build_provider_openai_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(KeyError):
        build_provider("openai")
