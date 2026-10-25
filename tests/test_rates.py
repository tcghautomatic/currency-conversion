import json

import pytest
import requests

from currency_converter.config import ConfigError
from currency_converter.rates import (
    ProviderError,
    RateTable,
    UnsupportedCurrencyError,
    build_user_agent,
    fetch_rate_table,
    get_json,
    normalise_exchangerate_fun,
    normalise_frankfurter,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.headers = {}

    def get(self, url, timeout=None, headers=None):
        self.calls.append({"url": url, "timeout": timeout, "headers": headers})
        for prefix, response in self.responses.items():
            if url.startswith(prefix):
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected url {url}")


def test_exchangerate_fun_normalises_rates_and_timestamp():
    payload = {
        "timestamp": 1792890008,
        "base": "AUD",
        "rates": {"USD": 0.703, "EUR": 0.627454},
    }
    table = normalise_exchangerate_fun(payload, base="AUD")
    assert table.base == "AUD"
    assert table.provider == "exchangerate.fun"
    assert table.rates == {"USD": 0.703, "EUR": 0.627454}
    assert table.dates == {}
    assert table.as_of == "2026-10-25T01:00:08+00:00"


def test_exchangerate_fun_rejects_bad_shape():
    with pytest.raises(ProviderError):
        normalise_exchangerate_fun({"base": "AUD"}, base="AUD")


def test_frankfurter_normalises_rows_and_dates():
    payload = [
        {"date": "2026-10-25", "base": "AUD", "quote": "USD", "rate": 0.70224},
        {"date": "2026-10-23", "base": "AUD", "quote": "EUR", "rate": 0.63},
    ]
    table = normalise_frankfurter(payload, base="AUD")
    assert table.base == "AUD"
    assert table.provider == "frankfurter.dev"
    assert table.rates == {"USD": 0.70224, "EUR": 0.63}
    assert table.dates == {"USD": "2026-10-25", "EUR": "2026-10-23"}
    assert table.as_of == "2026-10-25"


def test_frankfurter_rejects_empty_payload():
    with pytest.raises(ProviderError):
        normalise_frankfurter([], base="AUD")


ERF_PAYLOAD = {"timestamp": 1792890008, "base": "USD", "rates": {"AUD": 1.422475}}
FK_PAYLOAD = [{"date": "2026-10-25", "base": "USD", "quote": "AUD", "rate": 1.4253}]


def test_fetch_rate_table_uses_primary_when_available():
    session = FakeSession(
        {
            "https://api.exchangerate.fun": FakeResponse(200, ERF_PAYLOAD),
            "https://api.frankfurter.dev": FakeResponse(200, FK_PAYLOAD),
        }
    )
    table = fetch_rate_table("USD", session=session)
    assert table.provider == "exchangerate.fun"
    assert table.base == "USD"
    assert len(session.calls) == 1
    assert session.calls[0]["url"] == "https://api.exchangerate.fun/latest?base=USD"


def test_fetch_rate_table_falls_back_when_primary_is_down():
    session = FakeSession(
        {
            "https://api.exchangerate.fun": requests.ConnectionError("dns failure"),
            "https://api.frankfurter.dev": FakeResponse(200, FK_PAYLOAD),
        }
    )
    table = fetch_rate_table("USD", session=session)
    assert table.provider == "frankfurter.dev"
    assert len(session.calls) == 2
    assert session.calls[1]["url"] == "https://api.frankfurter.dev/v2/rates?base=USD"


def test_fetch_rate_table_falls_back_when_primary_returns_500():
    session = FakeSession(
        {
            "https://api.exchangerate.fun": FakeResponse(500, None, text="boom"),
            "https://api.frankfurter.dev": FakeResponse(200, FK_PAYLOAD),
        }
    )
    table = fetch_rate_table("USD", session=session)
    assert table.provider == "frankfurter.dev"


def test_fetch_rate_table_raises_when_both_providers_fail():
    session = FakeSession(
        {
            "https://api.exchangerate.fun": requests.ConnectionError("down"),
            "https://api.frankfurter.dev": FakeResponse(503, None, text="down"),
        }
    )
    with pytest.raises(ProviderError) as excinfo:
        fetch_rate_table("USD", session=session)
    assert "exchangerate.fun" in str(excinfo.value)
    assert "frankfurter.dev" in str(excinfo.value)


def test_fetch_rate_table_reports_unsupported_currency_when_both_reject():
    session = FakeSession(
        {
            "https://api.exchangerate.fun": FakeResponse(400, None, text='{"error":"currency is error"}'),
            "https://api.frankfurter.dev": FakeResponse(422, None, text='{"message":"invalid currency: ZZZ"}'),
        }
    )
    with pytest.raises(UnsupportedCurrencyError):
        fetch_rate_table("ZZZ", session=session)


def test_build_user_agent_uses_configured_email():
    agent = build_user_agent()
    assert agent.startswith("hermes-currency-converter/1.0 (+")
    assert agent.endswith(")")
    assert "@" in agent


def test_build_user_agent_raises_when_email_missing(tmp_path, monkeypatch):
    from currency_converter import config as config_module

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"contact_email": None}), encoding="utf-8")
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    with pytest.raises(ConfigError) as excinfo:
        build_user_agent()
    assert "must be populated" in str(excinfo.value)


def test_get_json_sends_contact_user_agent():
    session = FakeSession({"https://example.test": FakeResponse(200, {"ok": True})})
    assert get_json("https://example.test/x", session=session) == {"ok": True}
    call = session.calls[0]
    assert call["headers"]["User-Agent"] == build_user_agent()
    assert "(+" in call["headers"]["User-Agent"]
    assert call["timeout"] == 20.0


def test_get_json_raises_provider_error_on_connection_failure():
    session = FakeSession({"https://example.test": requests.ConnectionError("boom")})
    with pytest.raises(ProviderError):
        get_json("https://example.test/x", session=session)


def test_get_json_raises_provider_error_on_500():
    session = FakeSession({"https://example.test": FakeResponse(500, None, text="boom")})
    with pytest.raises(ProviderError):
        get_json("https://example.test/x", session=session)


def test_get_json_raises_unsupported_currency_on_rejected_code():
    session = FakeSession(
        {"https://example.test": FakeResponse(400, None, text='{"error":"currency is error"}')}
    )
    with pytest.raises(UnsupportedCurrencyError):
        get_json("https://example.test/x", session=session)


def test_get_json_raises_provider_error_on_non_json_body():
    session = FakeSession({"https://example.test": FakeResponse(200, None, text="<html>")})
    with pytest.raises(ProviderError):
        get_json("https://example.test/x", session=session)
