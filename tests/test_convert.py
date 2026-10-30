import pytest

from currency_converter.convert import ConversionError, convert

from tests.test_rates import FK_PAYLOAD, FakeResponse, FakeSession

ERF_AUD = {"timestamp": 1792890008, "base": "AUD", "rates": {"USD": 0.703, "EUR": 0.627454}}
ERF_USD = {"timestamp": 1792890008, "base": "USD", "rates": {"AUD": 1.422475, "EUR": 0.892538}}


def _session(erf_payload, fk_payload=None):
    return FakeSession(
        {
            "https://api.exchangerate.fun": FakeResponse(200, erf_payload),
            "https://api.frankfurter.dev": FakeResponse(200, fk_payload or FK_PAYLOAD),
        }
    )


def test_convert_usd_to_aud_divides_by_rate(tmp_path):
    session = _session(ERF_AUD)
    result = convert(100, "USD", "AUD", cache_dir=tmp_path, session=session)
    assert result["to_amount"] == pytest.approx(142.25, abs=0.01)
    assert result["from_currency"] == "USD"
    assert result["to_currency"] == "AUD"
    assert result["rate"] == 0.703
    assert result["provider"] == "exchangerate.fun"
    assert result["cached"] is False
    assert session.calls[0]["url"] == "https://api.exchangerate.fun/latest?base=AUD"


def test_convert_non_aud_target_switches_base(tmp_path):
    session = _session(ERF_USD)
    result = convert(100, "AUD", "USD", cache_dir=tmp_path, session=session)
    assert result["to_amount"] == pytest.approx(70.30, abs=0.01)
    assert result["rate"] == 1.422475
    assert session.calls[0]["url"] == "https://api.exchangerate.fun/latest?base=USD"


def test_convert_same_currency_is_identity(tmp_path):
    session = _session(ERF_AUD)
    result = convert(100, "AUD", "AUD", cache_dir=tmp_path, session=session)
    assert result["to_amount"] == pytest.approx(100.0)
    assert result["rate"] == 1.0


def test_convert_rejects_unknown_source_currency(tmp_path):
    session = _session(ERF_AUD)
    with pytest.raises(ConversionError) as excinfo:
        convert(100, "XYZ", "AUD", cache_dir=tmp_path, session=session)
    assert "XYZ" in str(excinfo.value)


def test_convert_rejects_bad_currency_code(tmp_path):
    with pytest.raises(ConversionError):
        convert(100, "US", "AUD", cache_dir=tmp_path)


def test_convert_rejects_non_finite_amount(tmp_path):
    with pytest.raises(ConversionError):
        convert(float("nan"), "USD", "AUD", cache_dir=tmp_path)


def test_convert_uses_cached_table_on_second_call(tmp_path):
    session = _session(ERF_AUD)
    first = convert(100, "USD", "AUD", cache_dir=tmp_path, session=session)
    second = convert(200, "USD", "AUD", cache_dir=tmp_path, session=session)
    assert len(session.calls) == 1
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["to_amount"] == pytest.approx(284.5, abs=0.05)


def test_convert_reports_cached_at_on_fresh_fetch(tmp_path):
    session = _session(ERF_AUD)
    result = convert(
        100, "USD", "AUD", cache_dir=tmp_path, session=session, now=1_800_000_000.0
    )
    assert result["cached_at"] == 1_800_000_000.0


def test_convert_reports_cached_at_from_cache_file(tmp_path):
    session = _session(ERF_AUD)
    convert(100, "USD", "AUD", cache_dir=tmp_path, session=session, now=1_800_000_000.0)
    result = convert(
        200,
        "USD",
        "AUD",
        cache_dir=tmp_path,
        session=session,
        now=1_800_000_000.0 + 120,
    )
    assert result["cached"] is True
    assert result["cache_age_seconds"] == pytest.approx(120.0, abs=0.01)
    assert result["cached_at"] == 1_800_000_000.0


def test_convert_refetches_when_cache_is_stale(tmp_path):
    session = _session(ERF_AUD)
    convert(100, "USD", "AUD", cache_dir=tmp_path, session=session, now=1_800_000_000.0)
    convert(100, "USD", "AUD", cache_dir=tmp_path, session=session, now=1_800_000_000.0 + 3601)
    assert len(session.calls) == 2
