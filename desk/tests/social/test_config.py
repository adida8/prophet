"""SocialConfig env-parsing tests."""

from __future__ import annotations

import pytest

from desk.social import load_config


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in [
        "DESK_SOCIAL_ENABLED", "DESK_SOCIAL_DB_PATH", "DESK_SOCIAL_ASSETS_DIR",
        "DESK_SOCIAL_MIN_EDGE_PP", "DESK_SOCIAL_WEEKLY_DAY",
        "DESK_SOCIAL_WEEKLY_AT", "DESK_SOCIAL_PUBLISH_MODE",
        "IG_ACCESS_TOKEN", "IG_BUSINESS_ACCOUNT_ID",
        "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET",
    ]:
        monkeypatch.delenv(k, raising=False)
    cfg = load_config()
    assert cfg.enabled is False
    assert cfg.min_edge_pp == 2.0
    assert cfg.weekly_day == "sunday"
    assert cfg.weekly_at  == "09:00"
    assert cfg.publish_mode == "manual"


def test_enabled_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_SOCIAL_ENABLED", "1")
    cfg = load_config()
    assert cfg.enabled is True


def test_bad_min_edge_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_SOCIAL_MIN_EDGE_PP", "not-a-number")
    with pytest.raises(ValueError):
        load_config()


def test_bad_weekday_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_SOCIAL_WEEKLY_DAY", "funday")
    with pytest.raises(ValueError):
        load_config()


def test_bad_clock_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_SOCIAL_WEEKLY_AT", "9-00")
    with pytest.raises(ValueError):
        load_config()


def test_bad_publish_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_SOCIAL_PUBLISH_MODE", "auto")
    with pytest.raises(ValueError):
        load_config()


def test_api_mode_requires_full_phase2_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_SOCIAL_PUBLISH_MODE", "api")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "tok")
    # Missing the rest — should raise.
    with pytest.raises(ValueError):
        load_config()


def test_api_mode_all_creds_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESK_SOCIAL_PUBLISH_MODE", "api")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("IG_BUSINESS_ACCOUNT_ID", "id")
    monkeypatch.setenv("X_API_KEY", "k")
    monkeypatch.setenv("X_API_SECRET", "s")
    monkeypatch.setenv("X_ACCESS_TOKEN", "t")
    monkeypatch.setenv("X_ACCESS_SECRET", "ts")
    cfg = load_config()
    assert cfg.publish_mode == "api"
    assert cfg.ig_access_token == "tok"
