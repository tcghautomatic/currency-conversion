"""Conversion orchestration: resolve rates, compute the amount, shape the result."""

from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .cache import DEFAULT_TTL_SECONDS, default_cache_dir, load_table, save_table
from .rates import RateTable, fetch_rate_table

CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")


class ConversionError(RuntimeError):
    """A conversion could not be completed."""


def normalise_currency(code: str) -> str:
    """Uppercase and validate a 3-letter currency code."""
    normalised = str(code).strip().upper()
    if not CURRENCY_CODE_RE.match(normalised):
        raise ConversionError(
            f"invalid currency code {code!r}: expected three letters, for example 'USD'"
        )
    return normalised


def resolve_rate_table(
    base: str,
    cache_dir=None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    use_cache: bool = True,
    session=None,
    now: Optional[float] = None,
) -> tuple[RateTable, bool, Optional[float], Optional[float]]:
    """Return `(table, cached, age_seconds, cached_at)`.

    Order of preference: fresh cache entry, then exchangerate.fun, then
    frankfurter.dev. A successful provider fetch refreshes the cache.

    `cached_at` is the raw epoch timestamp of the cache file's write, whether the
    entry was read from the cache or freshly written.
    """
    directory = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    if use_cache and ttl_seconds > 0:
        cached_table, age, cached_at = load_table(
            directory, base, ttl_seconds=ttl_seconds, now=now
        )
        if cached_table is not None:
            return cached_table, True, age, cached_at
    table = fetch_rate_table(base, session=session)
    current = time.time() if now is None else now
    save_table(directory, table, now=current)
    return table, False, None, current


def convert(
    from_amount: float,
    from_currency: str,
    to_currency: str = "AUD",
    *,
    cache_dir=None,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    use_cache: bool = True,
    session=None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Convert `from_amount` of `from_currency` into `to_currency`.

    Rates are always requested with `base = to_currency`, so the converted
    amount is `from_amount / rates[from_currency]`.
    """
    try:
        amount = float(from_amount)
    except (TypeError, ValueError) as exc:
        raise ConversionError(f"invalid amount {from_amount!r}") from exc
    if not math.isfinite(amount):
        raise ConversionError(f"amount must be a finite number, got {from_amount!r}")

    source = normalise_currency(from_currency)
    target = normalise_currency(to_currency)
    base = target  # per spec: the request base follows the target currency

    table, cached, age, cached_at = resolve_rate_table(
        base,
        cache_dir=cache_dir,
        ttl_seconds=ttl_seconds,
        use_cache=use_cache,
        session=session,
        now=now,
    )

    if source == base:
        rate = 1.0
    else:
        rate = table.rates.get(source)
        if rate is None:
            raise ConversionError(
                f"currency {source} is not supported by {table.provider}; "
                f"cannot convert {source} to {target}"
            )
        if rate <= 0:
            raise ConversionError(
                f"{table.provider} returned a non-positive rate for {source}"
            )

    converted = amount / rate
    return {
        "from_amount": amount,
        "from_currency": source,
        "to_currency": target,
        "to_amount": round(converted, 2),
        "to_amount_unrounded": converted,
        "rate": rate,
        "rate_description": f"1 {target} = {rate} {source}",
        "base": base,
        "as_of": table.dates.get(source) or table.as_of,
        "provider": table.provider,
        "cached": cached,
        "cache_age_seconds": round(age, 3) if age is not None else None,
        "cached_at": cached_at,
    }
