"""One-hour on-disk cache of normalised rate tables.

One JSON file per base currency, e.g. ``rates_AUD.json``.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional, Tuple

from .rates import RateTable

DEFAULT_TTL_SECONDS = 3600  # one hour, matching the providers' refresh cadence


def default_cache_dir() -> Path:
    """`$CURRENCY_CONVERTER_CACHE_DIR`, else `$XDG_CACHE_HOME/currency-converter`, else `~/.cache/currency-converter`."""
    override = os.environ.get("CURRENCY_CONVERTER_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "currency-converter"


def cache_path(cache_dir, base: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", base.upper())
    return Path(cache_dir) / f"rates_{safe}.json"


def load_table(
    cache_dir,
    base: str,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: Optional[float] = None,
) -> Tuple[Optional[RateTable], Optional[float], Optional[float]]:
    """Return `(table, age_seconds, cached_at)` when a fresh entry exists, else `(None, None, None)`.

    `cached_at` is the epoch timestamp recorded when the entry was written, i.e.
    when the rates were fetched and the cache file created.
    """
    current = time.time() if now is None else now
    path = cache_path(cache_dir, base)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None, None
    try:
        fetched_at = float(payload["fetched_at"])
        table = RateTable(
            base=str(payload["base"]).upper(),
            rates={str(k).upper(): float(v) for k, v in payload["rates"].items()},
            provider=str(payload["provider"]),
            as_of=str(payload.get("as_of", "")),
            dates={str(k).upper(): str(v) for k, v in (payload.get("dates") or {}).items()},
        )
    except (KeyError, TypeError, ValueError):
        return None, None, None
    age = current - fetched_at
    if age < 0 or age > ttl_seconds:
        return None, None, None
    return table, age, fetched_at


def save_table(cache_dir, table: RateTable, now: Optional[float] = None) -> Path:
    """Write `table` to the cache and return the path written."""
    current = time.time() if now is None else now
    path = cache_path(cache_dir, table.base)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base": table.base,
        "provider": table.provider,
        "as_of": table.as_of,
        "rates": dict(table.rates),
        "dates": dict(table.dates),
        "fetched_at": current,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path
