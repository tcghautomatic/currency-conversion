"""Runtime configuration loaded from `config.json` next to this module.

The contact email is kept out of the source so it can be changed without
touching code, and so it can be excluded from version control.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_FILENAME = "config.json"
CONFIG_PATH = Path(__file__).parent / CONFIG_FILENAME

CONTACT_EMAIL_KEY = "contact_email"


class ConfigError(RuntimeError):
    """Configuration is missing, unreadable, or incomplete."""


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and parse the config file. Raises ConfigError if it cannot be read."""
    target = Path(path) if path is not None else CONFIG_PATH
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"config file {target} could not be read: {exc}. "
            f"The contact email must be populated in {target}."
        ) from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ConfigError(
            f"config file {target} is not valid JSON: {exc}. "
            f"The contact email must be populated in {target}."
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"config file {target} must contain a JSON object. "
            f"The contact email must be populated in {target}."
        )
    return data


def contact_email(path: Optional[Path] = None) -> str:
    """Return the configured contact email.

    Raises ConfigError if the email is absent, null, or blank.
    """
    data = load_config(path)
    value = data.get(CONTACT_EMAIL_KEY)
    if value is None or not str(value).strip():
        raise ConfigError(
            f"The contact email must be populated in {CONFIG_PATH if path is None else path} "
            f"(key: {CONTACT_EMAIL_KEY!r})."
        )
    return str(value).strip()
