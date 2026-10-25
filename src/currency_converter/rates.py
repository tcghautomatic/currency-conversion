"""Rate sources: primary exchangerate.fun, fallback frankfurter.dev.

Two providers with two different payload shapes are normalised into one
`RateTable`:

    rates[X] = units of X per 1 unit of base
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .config import contact_email

# The contact address is included so the operators can be reached if traffic
# becomes abusive. It is read from config.json at request time.
USER_AGENT_TEMPLATE = "hermes-currency-converter/1.0 (+{email})"

DEFAULT_TIMEOUT_SECONDS = 20.0

EXCHANGERATE_FUN_URL = "https://api.exchangerate.fun/latest?base={base}"
FRANKFURTER_URL = "https://api.frankfurter.dev/v2/rates?base={base}"


def build_user_agent() -> str:
    """Build the User-Agent from the configured contact email.

    Raises ConfigError if the email is missing or blank.
    """
    return USER_AGENT_TEMPLATE.format(email=contact_email())


@dataclass(frozen=True)
class RateTable:
    """Normalised rates for one base currency."""

    base: str
    rates: Mapping[str, float]
    provider: str
    as_of: str
    dates: Mapping[str, str]


class ProviderError(RuntimeError):
    """A provider could not supply a usable rate table."""


class UnsupportedCurrencyError(ProviderError):
    """A provider explicitly rejected the requested currency code."""


def get_json(url: str, session=None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """GET `url` and return parsed JSON, or raise ProviderError."""
    import requests  # imported lazily so tests can inject a fake session

    active = session if session is not None else requests.Session()
    try:
        response = active.get(
            url,
            timeout=timeout,
            headers={"User-Agent": build_user_agent(), "Accept": "application/json"},
        )
    except (requests.RequestException, OSError) as exc:
        # Network-level failure: DNS, TLS, timeout, connection reset.
        raise ProviderError(f"request to {url} failed: {exc}") from exc
    if response.status_code != 200:
        body = (response.text or "")[:300].lower()
        if "invalid currency" in body or "currency is error" in body:
            raise UnsupportedCurrencyError(
                f"{url} rejected the currency code (HTTP {response.status_code})"
            )
        raise ProviderError(f"{url} returned HTTP {response.status_code}")
    try:
        return response.json()
    except Exception as exc:
        raise ProviderError(f"{url} returned a non-JSON body: {exc}") from exc


def fetch_rate_table(base: str, session=None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> RateTable:
    """Return a rate table for `base`, trying exchangerate.fun then frankfurter.dev."""
    base = base.upper()
    providers = (
        ("exchangerate.fun", EXCHANGERATE_FUN_URL, normalise_exchangerate_fun),
        ("frankfurter.dev", FRANKFURTER_URL, normalise_frankfurter),
    )
    errors: list[str] = []
    rejected = False
    for name, url_template, normalise in providers:
        url = url_template.format(base=base)
        try:
            payload = get_json(url, session=session, timeout=timeout)
            return normalise(payload, base=base)
        except UnsupportedCurrencyError as exc:
            rejected = True
            errors.append(f"{name}: {exc}")
        except ProviderError as exc:
            errors.append(f"{name}: {exc}")
    message = "; ".join(errors)
    if rejected:
        raise UnsupportedCurrencyError(message)
    raise ProviderError(f"all rate providers failed: {message}")


def normalise_exchangerate_fun(payload: Any, base: str) -> RateTable:
    """Normalise an exchangerate.fun `/latest` payload."""
    if not isinstance(payload, dict):
        raise ProviderError("exchangerate.fun returned a non-object payload")
    raw_rates = payload.get("rates")
    if not isinstance(raw_rates, dict) or not raw_rates:
        raise ProviderError("exchangerate.fun payload has no usable 'rates' object")
    try:
        rates = {str(k).upper(): float(v) for k, v in raw_rates.items()}
    except (TypeError, ValueError) as exc:
        raise ProviderError(f"exchangerate.fun returned a non-numeric rate: {exc}") from exc
    timestamp = payload.get("timestamp")
    as_of = ""
    if timestamp is not None:
        as_of = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat()
    return RateTable(
        base=base.upper(),
        rates=rates,
        provider="exchangerate.fun",
        as_of=as_of,
        dates={},
    )


def normalise_frankfurter(payload: Any, base: str) -> RateTable:
    """Normalise a frankfurter.dev `/v2/rates` payload (an array of rows)."""
    if not isinstance(payload, list):
        raise ProviderError("frankfurter.dev returned a non-array payload")
    rates: dict[str, float] = {}
    dates: dict[str, str] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        quote = str(row.get("quote", "")).strip().upper()
        if not quote or row.get("rate") is None:
            continue
        try:
            rates[quote] = float(row["rate"])
        except (TypeError, ValueError):
            continue
        date = row.get("date")
        if date:
            dates[quote] = str(date)
    if not rates:
        raise ProviderError("frankfurter.dev payload contained no usable rates")
    as_of = max(dates.values()) if dates else ""
    return RateTable(
        base=base.upper(),
        rates=rates,
        provider="frankfurter.dev",
        as_of=as_of,
        dates=dates,
    )
