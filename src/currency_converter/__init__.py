"""Currency conversion with exchangerate.fun primary and frankfurter.dev fallback."""

from .convert import ConversionError, convert

__all__ = ["ConversionError", "convert"]
__version__ = "0.1.0"
