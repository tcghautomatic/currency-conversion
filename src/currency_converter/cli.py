"""Command line interface: parse args, print a structured JSON result."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from .cache import DEFAULT_TTL_SECONDS
from .config import ConfigError
from .convert import ConversionError, convert
from .rates import ProviderError, UnsupportedCurrencyError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="currency-converter",
        description=(
            "Convert an amount between currencies. Rates come from "
            "exchangerate.fun, falling back to frankfurter.dev, and are cached for one hour."
        ),
    )
    parser.add_argument("--from-amount", type=float, required=True, help="Amount to convert, e.g. 100")
    parser.add_argument("--from-currency", required=True, help="Source currency code, e.g. USD")
    parser.add_argument(
        "--to-currency",
        default="AUD",
        help="Target currency code (default: AUD)",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for the rate cache (default: $CURRENCY_CONVERTER_CACHE_DIR or ~/.cache/currency-converter)",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=DEFAULT_TTL_SECONDS,
        help="Cache lifetime in seconds (default: 3600)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore any cached rates and fetch fresh ones",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None, session=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = convert(
            args.from_amount,
            args.from_currency,
            args.to_currency,
            cache_dir=args.cache_dir,
            ttl_seconds=args.cache_ttl,
            use_cache=not args.no_cache,
            session=session,
        )
    except (ConfigError, ConversionError, ProviderError, UnsupportedCurrencyError) as exc:
        print(
            json.dumps({"error": str(exc), "error_type": type(exc).__name__}, indent=2),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
