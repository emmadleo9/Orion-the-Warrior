"""Tests for the dependency-free .env loader."""

import os

import pytest

from orion_app import config


@pytest.fixture(autouse=True)
def clean_instagram_env(monkeypatch):
    monkeypatch.delenv("ORION_INSTAGRAM_APP_ID", raising=False)
    monkeypatch.delenv("ORION_INSTAGRAM_APP_SECRET", raising=False)
    monkeypatch.delenv("ORION_TEST_ONLY_KEY", raising=False)


def test_load_env_file_reads_key_values(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\n"
        "\n"
        "ORION_INSTAGRAM_APP_ID=1234567890\n"
        "ORION_INSTAGRAM_APP_SECRET='super-secret'\n"
        "ORION_TEST_ONLY_KEY=\"quoted value\"\n",
        encoding="utf-8",
    )

    assert config.load_env_file(env_file) is True
    assert os.environ["ORION_INSTAGRAM_APP_ID"] == "1234567890"
    assert os.environ["ORION_INSTAGRAM_APP_SECRET"] == "super-secret"
    assert os.environ["ORION_TEST_ONLY_KEY"] == "quoted value"


def test_load_env_file_does_not_override_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("ORION_INSTAGRAM_APP_ID", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("ORION_INSTAGRAM_APP_ID=from-file\n", encoding="utf-8")

    config.load_env_file(env_file)

    assert os.environ["ORION_INSTAGRAM_APP_ID"] == "from-shell"


def test_load_env_file_override_when_requested(tmp_path, monkeypatch):
    monkeypatch.setenv("ORION_INSTAGRAM_APP_ID", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("ORION_INSTAGRAM_APP_ID=from-file\n", encoding="utf-8")

    config.load_env_file(env_file, override=True)

    assert os.environ["ORION_INSTAGRAM_APP_ID"] == "from-file"


def test_load_env_file_handles_export_prefix_and_missing_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("export ORION_TEST_ONLY_KEY=exported\n", encoding="utf-8")

    assert config.load_env_file(env_file) is True
    assert os.environ["ORION_TEST_ONLY_KEY"] == "exported"
    assert config.load_env_file(tmp_path / "does-not-exist") is False


def test_loaded_env_reaches_instagram_integration(tmp_path):
    """A value placed in a .env file must be visible to the integration."""
    from orion_app.instagram import InstagramIntegration

    env_file = tmp_path / ".env"
    env_file.write_text(
        "ORION_INSTAGRAM_APP_ID=app-id-from-file\n"
        "ORION_INSTAGRAM_APP_SECRET=app-secret-from-file\n",
        encoding="utf-8",
    )
    config.load_env_file(env_file)

    integration = InstagramIntegration()

    assert integration.configured is True
    assert integration.app_id == "app-id-from-file"
