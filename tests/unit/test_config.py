"""Configuration behavior tests."""

from __future__ import annotations

from core.config import DEFAULT_REGIONS, Settings


def test_defaults_are_sane() -> None:
    settings = Settings()
    assert settings.app_name == "CloudCostLens"
    assert settings.demo_mode is True
    assert settings.api_base_path == "/api/v1"
    assert settings.default_regions == list(DEFAULT_REGIONS)


def test_csv_list_parsing() -> None:
    settings = Settings(
        cors_origins="http://a.test, http://b.test",
        default_regions="us-east-1,eu-west-1",
    )
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
    assert settings.default_regions == ["us-east-1", "eu-west-1"]


def test_production_requires_secrets() -> None:
    settings = Settings(environment="production", secret_key="dev-insecure-change-me")
    try:
        settings.validate_for_runtime()
    except RuntimeError as exc:
        assert "SECRET_KEY" in str(exc)
    else:  # pragma: no cover - guard
        raise AssertionError("expected production misconfiguration to raise")


def test_freshness_flags() -> None:
    assert Settings(environment="test").is_test is True
    assert Settings(environment="production", secret_key="x").is_production is True
