"""Shared test fixtures.

The contact email lives in a per-machine `config.json` that is gitignored, so it
is absent from a fresh clone. Every test therefore runs against a temporary
config pointing at a placeholder address, keeping the suite self-contained and
independent of the developer's local file.
"""

import json

import pytest

from currency_converter import config as config_module

TEST_CONTACT_EMAIL = "test@example.com"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point the config loader at a temporary file for the duration of each test."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"contact_email": TEST_CONTACT_EMAIL}), encoding="utf-8")
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    return path
