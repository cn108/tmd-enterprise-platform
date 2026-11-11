"""Environment variable helpers.

Every setting that differs between local, staging and production is read here
rather than hard-coded. Missing values raise at start-up instead of failing
later, and no secret has a usable default in production.
"""

from __future__ import annotations

import os

_TRUE = {"1", "true", "yes", "on"}


def env_str(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"Environment variable {name} is required and was not set. "
            "Copy .env.example to .env and fill it in, or set it in the deployment environment."
        )
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]
