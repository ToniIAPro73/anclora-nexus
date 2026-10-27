import asyncio
import os

os.environ.setdefault("AI_RUNTIME_PROFILE", "groq-cloudflare")
os.environ.setdefault("GROQ_API_KEY", "groq-test")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "cf-account-test")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "cf-token-test")
os.environ.setdefault("INTERNAL_AUDIT_SECRET", "test-secret")

from backend.config import settings
from backend.services.ai_runtime import get_runtime_summary, get_task_runtime_routes
from backend.services.llm_service import LLMService


def test_groq_cloudflare_runtime_routes(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_RUNTIME_PROFILE", "groq-cloudflare")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "groq-key")
    monkeypatch.setattr(settings, "CLOUDFLARE_ACCOUNT_ID", "cf-account")
    monkeypatch.setattr(settings, "CLOUDFLARE_API_TOKEN", "cf-token")

    routes = get_task_runtime_routes()

    assert routes["analyze"].provider == "groq"
    assert routes["analyze"].model == settings.GROQ_MODEL_PRIMARY
    assert routes["summarize"].provider == "groq"
    assert routes["summarize"].model == settings.GROQ_MODEL_FAST
    assert routes["generate_copy"].provider == "cloudflare"
    assert routes["generate_copy"].model == settings.CLOUDFLARE_MODEL_PRIMARY


def test_runtime_summary_surfaces_missing_env(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_RUNTIME_PROFILE", "groq-cloudflare")
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    monkeypatch.setattr(settings, "CLOUDFLARE_ACCOUNT_ID", None)
    monkeypatch.setattr(settings, "CLOUDFLARE_AI_BASE_URL", None)
    monkeypatch.setattr(settings, "CLOUDFLARE_API_TOKEN", None)
    monkeypatch.setattr(settings, "INTERNAL_AUDIT_SECRET", None)

    summary = get_runtime_summary()

    assert summary["status"] == "degraded"
    assert "GROQ_API_KEY" in summary["missing_env"]
    assert "CLOUDFLARE_API_TOKEN" in summary["missing_env"]
    assert summary["audit_secret_configured"] is False


def test_llm_service_degrades_without_ready_runtime(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_RUNTIME_PROFILE", "groq-cloudflare")
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    monkeypatch.setattr(settings, "CLOUDFLARE_ACCOUNT_ID", None)
    monkeypatch.setattr(settings, "CLOUDFLARE_AI_BASE_URL", None)
    monkeypatch.setattr(settings, "CLOUDFLARE_API_TOKEN", None)

    service = LLMService()
    result = asyncio.run(service.analyze("analiza esto"))

    assert "Analysis failed" in result
