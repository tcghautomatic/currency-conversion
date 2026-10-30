# currency-converter

Convert an amount between currencies.

- Primary rate source: `https://api.exchangerate.fun/latest?base=<BASE>`
- Fallback: `https://api.frankfurter.dev/v2/rates?base=<BASE>`
- Rates are cached on disk for one hour (one file per base currency).
- Every request sends `User-Agent: hermes-currency-converter/1.0 (+<contact_email>)`.
- The request `base` follows the target currency: converting to `AUD` uses `base=AUD`,
  converting to `USD` uses `base=USD`.

## Attribution

Exchange rates are provided by these services, and this project is not affiliated
with or endorsed by them:

- [exchangerate.fun](https://www.exchangerate.fun/) - primary rate source
- [frankfurter.dev](https://frankfurter.dev/) - fallback rate source, powered by
  reference data published by the European Central Bank

Please consider supporting both projects if you use them.

## Configuration

The contact email used in the User-Agent lives in `src/currency_converter/config.json`:

```json
{
  "contact_email": "you@example.com"
}
```

That file is gitignored (it is per-machine and holds a contact address), so on a fresh
clone create it from the template:

```bash
cp src/currency_converter/config.example.json src/currency_converter/config.json
```

If `contact_email` is missing, null, or blank, the tool refuses to make a request and
exits with an error saying the email must be populated:

```json
{
  "error": "The contact email must be populated in /path/to/config.json (key: 'contact_email').",
  "error_type": "ConfigError"
}
```

## Install

```bash
uv sync
```

## Usage

```bash
uv run currency-converter --from-amount 100 --from-currency USD
uv run currency-converter --from-amount 100 --from-currency AUD --to-currency USD
uv run currency-converter --from-amount 100 --from-currency USD --no-cache
```

Output is JSON on stdout:

```json
{
  "from_amount": 100.0,
  "from_currency": "USD",
  "to_currency": "AUD",
  "to_amount": 142.25,
  "to_amount_unrounded": 142.2475106685633,
  "rate": 0.703,
  "rate_description": "1 AUD = 0.703 USD",
  "base": "AUD",
  "as_of": "2026-10-25T01:00:08+00:00",
  "provider": "exchangerate.fun",
  "cached": false,
  "cache_age_seconds": null,
  "cached_at": 1793357478.512837
}
```

`cached_at` is the raw Unix timestamp (epoch seconds) of when the cache file was
written. It is set whether the rates were served from the cache or freshly fetched and
cached, so it always points at the on-disk entry that backs the result.
`cache_age_seconds` is `null` on a fresh fetch, since there was no cached entry to age.

Errors go to stderr as JSON with a non-zero exit code:

```json
{
  "error": "currency ZZZ is not supported by exchangerate.fun; cannot convert ZZZ to AUD",
  "error_type": "ConversionError"
}
```

`error_type` is one of:

- `ConfigError` - the contact email is missing or null in `config.json`.
- `ConversionError` - bad input, or the source currency is not in the rate table.
- `UnsupportedCurrencyError` - both providers explicitly rejected the requested base currency.
- `ProviderError` - both providers were unreachable or returned an unusable response.

## Library use

```python
from currency_converter import convert

result = convert(100, "USD", "AUD")
print(result["to_amount"])
```

## Cache

Files live in `$CURRENCY_CONVERTER_CACHE_DIR`, else `$XDG_CACHE_HOME/currency-converter`,
else `~/.cache/currency-converter`. One file per base currency, e.g. `rates_AUD.json`.
Override per call with `--cache-dir`, or bypass with `--no-cache`.

## Notes

- `to_amount` is rounded to 2 decimals; `to_amount_unrounded` keeps full precision
  (useful for currencies with 0 or 3 decimal places).
- exchangerate.fun covers 168 currencies including `BTC`; frankfurter.dev covers 165
  and has no `BTC`, so a `BTC` conversion only works while the primary is healthy.
- frankfurter.dev publishes per-currency dates, so a fallback result may mix rates
  from adjacent days. `as_of` reports the date for the source currency actually used.
- See [Attribution](#attribution) for the rate providers.

## Tests

```bash
uv run pytest -v
```

The test suite is fully offline: a fake session is injected, so no test touches the network.
