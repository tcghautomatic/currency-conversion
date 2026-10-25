import json

from currency_converter.cache import (
    DEFAULT_TTL_SECONDS,
    cache_path,
    load_table,
    save_table,
)
from currency_converter.rates import RateTable

NOW = 1_800_000_000.0


def _table(base="AUD"):
    return RateTable(
        base=base,
        rates={"USD": 0.703, "EUR": 0.627454},
        provider="exchangerate.fun",
        as_of="2026-10-25T01:00:08+00:00",
        dates={},
    )


def test_cache_path_is_per_base_currency(tmp_path):
    assert cache_path(tmp_path, "AUD").name == "rates_AUD.json"
    assert cache_path(tmp_path, "usd").name == "rates_USD.json"


def test_save_then_load_roundtrip(tmp_path):
    save_table(tmp_path, _table(), now=NOW)
    table, age = load_table(tmp_path, "AUD", now=NOW)
    assert table.rates == {"USD": 0.703, "EUR": 0.627454}
    assert table.provider == "exchangerate.fun"
    assert table.as_of == "2026-10-25T01:00:08+00:00"
    assert age == 0.0


def test_load_returns_none_when_expired(tmp_path):
    save_table(tmp_path, _table(), now=NOW)
    table, age = load_table(tmp_path, "AUD", now=NOW + DEFAULT_TTL_SECONDS + 1)
    assert table is None
    assert age is None


def test_load_returns_none_when_missing(tmp_path):
    table, age = load_table(tmp_path, "AUD", now=NOW)
    assert table is None
    assert age is None


def test_load_returns_none_for_corrupt_file(tmp_path):
    path = cache_path(tmp_path, "AUD")
    path.write_text("{not json", encoding="utf-8")
    table, age = load_table(tmp_path, "AUD", now=NOW)
    assert table is None
    assert age is None


def test_cache_file_records_fetched_at(tmp_path):
    save_table(tmp_path, _table(), now=NOW)
    payload = json.loads(cache_path(tmp_path, "AUD").read_text(encoding="utf-8"))
    assert payload["fetched_at"] == NOW
    assert payload["base"] == "AUD"
    assert payload["rates"]["USD"] == 0.703
