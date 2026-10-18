"""HTTP routing for the Worker, kept free of Workers imports so it can be tested."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from . import client
from .exceptions import ClearOutsideError, FetchError, InvalidLocationError, ParseError

DEFAULT_CACHE_TTL = 900

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"", "0", "false", "no", "off"}


class _BadRequest(Exception):
    pass


def _flag(query: dict[str, list[str]], name: str, default: bool) -> bool:
    values = query.get(name)
    if not values:
        return default
    value = values[-1].strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise _BadRequest(f"{name} must be a boolean (1/0, true/false), got {values[-1]!r}")


def _units(query: dict[str, list[str]]) -> bool:
    """Return True for metric."""
    values = query.get("units")
    if not values:
        return True
    value = values[-1].strip().lower()
    if value not in ("metric", "imperial"):
        raise _BadRequest(f"units must be 'metric' or 'imperial', got {values[-1]!r}")
    return value == "metric"


def _index(base: str) -> dict[str, Any]:
    from . import __version__

    return {
        "name": "ClearOutsideAPY",
        "version": __version__,
        "description": "7-day hourly astronomy forecast scraped from clearoutside.com",
        "endpoints": {
            "GET /forecast/{lat}/{lon}": {
                "view": f"one of {', '.join(client.VIEWS)} (default midday)",
                "experimental": "1 to include Met.no / 7Timer rows (default 0)",
                "units": "metric or imperial (default metric)",
            },
        },
        "example": f"{base}/forecast/43.16/-75.84?view=midday",
        "source": "https://github.com/TheElevatedOne/ClearOutsideAPY",
    }


def _error(status: int, exc: Exception | str, kind: str | None = None):
    message = str(exc)
    kind = kind or type(exc).__name__
    return status, {"error": {"type": kind, "message": message}}


async def route(method: str, url: str, *, cache_ttl: int = DEFAULT_CACHE_TTL):
    """Return ``(status, payload)``; ``payload`` is a JSON-able object or None."""
    parts = urlsplit(url)
    segments = [unquote(s) for s in parts.path.split("/") if s]
    query = parse_qs(parts.query, keep_blank_values=True)

    if method == "OPTIONS":
        return 204, None
    if method != "GET":
        return _error(405, f"method {method} not allowed", "MethodNotAllowed")

    if not segments:
        return 200, _index(f"{parts.scheme}://{parts.netloc}")

    if segments[0] != "forecast":
        return _error(404, f"no route for {parts.path}", "NotFound")
    if len(segments) != 3:
        return _error(404, "use /forecast/{lat}/{lon}", "NotFound")

    try:
        return 200, await client.fetch_forecast(
            segments[1],
            segments[2],
            view=(query.get("view") or ["midday"])[-1],
            experimental=_flag(query, "experimental", False),
            metric=_units(query),
            cache_ttl=cache_ttl,
        )
    except _BadRequest as exc:
        return _error(400, exc, "BadRequest")
    except InvalidLocationError as exc:
        return _error(400, exc)
    except (FetchError, ParseError) as exc:
        return _error(502, exc)
    except ClearOutsideError as exc:
        return _error(500, exc)


def cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Max-Age": "86400",
    }


async def handle(method: str, url: str, *, cache_ttl: int = DEFAULT_CACHE_TTL):
    """Route a request and return ``(status, body, headers)`` ready for a Response."""
    status, payload = await route(method, url, cache_ttl=cache_ttl)
    headers = cors_headers()
    if status == 204:
        return status, None, headers
    headers["Content-Type"] = "application/json; charset=utf-8"
    if status == 200 and cache_ttl > 0:
        headers["Cache-Control"] = f"public, max-age={cache_ttl}"
    else:
        headers["Cache-Control"] = "no-store"
    if status == 405:
        headers["Allow"] = "GET, OPTIONS"
    return status, json.dumps(payload, ensure_ascii=False), headers
