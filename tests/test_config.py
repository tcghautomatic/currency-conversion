import json

import pytest

from currency_converter.config import ConfigError, contact_email, load_config


def _write(tmp_path, payload):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_contact_email_returns_configured_value(tmp_path):
    path = _write(tmp_path, {"contact_email": "someone@example.com"})
    assert contact_email(path) == "someone@example.com"


def test_contact_email_strips_whitespace(tmp_path):
    path = _write(tmp_path, {"contact_email": "  someone@example.com  "})
    assert contact_email(path) == "someone@example.com"


def test_contact_email_raises_when_null(tmp_path):
    path = _write(tmp_path, {"contact_email": None})
    with pytest.raises(ConfigError) as excinfo:
        contact_email(path)
    assert "must be populated" in str(excinfo.value)


def test_contact_email_raises_when_empty(tmp_path):
    path = _write(tmp_path, {"contact_email": "   "})
    with pytest.raises(ConfigError) as excinfo:
        contact_email(path)
    assert "must be populated" in str(excinfo.value)


def test_contact_email_raises_when_key_missing(tmp_path):
    path = _write(tmp_path, {})
    with pytest.raises(ConfigError) as excinfo:
        contact_email(path)
    assert "must be populated" in str(excinfo.value)


def test_load_config_raises_when_file_missing(tmp_path):
    with pytest.raises(ConfigError) as excinfo:
        load_config(tmp_path / "nope.json")
    assert "must be populated" in str(excinfo.value)


def test_load_config_raises_on_invalid_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)
