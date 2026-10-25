import json

import pytest

from currency_converter.cli import main

from tests.test_convert import ERF_AUD
from tests.test_rates import FK_PAYLOAD, FakeResponse, FakeSession


def _session():
    return FakeSession(
        {
            "https://api.exchangerate.fun": FakeResponse(200, ERF_AUD),
            "https://api.frankfurter.dev": FakeResponse(200, FK_PAYLOAD),
        }
    )


def test_cli_prints_json_result(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CURRENCY_CONVERTER_CACHE_DIR", str(tmp_path))
    exit_code = main(["--from-amount", "100", "--from-currency", "USD"], session=_session())
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["from_currency"] == "USD"
    assert payload["to_currency"] == "AUD"
    assert payload["to_amount"] == pytest.approx(142.25, abs=0.01)


def test_cli_defaults_to_aud(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CURRENCY_CONVERTER_CACHE_DIR", str(tmp_path))
    exit_code = main(["--from-amount", "100", "--from-currency", "USD"], session=_session())
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["to_currency"] == "AUD"


def test_cli_requires_from_amount(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--from-currency", "USD"])
    assert excinfo.value.code == 2


def test_cli_reports_errors_on_stderr(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CURRENCY_CONVERTER_CACHE_DIR", str(tmp_path))
    exit_code = main(["--from-amount", "100", "--from-currency", "US"], session=_session())
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert "error" in payload
    assert payload["error_type"] == "ConversionError"


def test_cli_reports_missing_contact_email(capsys, tmp_path, monkeypatch):
    from currency_converter import config as config_module

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"contact_email": None}), encoding="utf-8")
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    exit_code = main(["--from-amount", "100", "--from-currency", "USD"], session=_session())
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error_type"] == "ConfigError"
    assert "must be populated" in payload["error"]
