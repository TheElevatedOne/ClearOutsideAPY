from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from clear_outside_apy.api import handle
from clear_outside_apy.exceptions import FetchError

FIXTURES = Path(__file__).parent / "fixtures"
MIDDAY = (FIXTURES / "forecast_midday.html").read_bytes()
BASE = "https://api.example.workers.dev"


def call(method, path, html=MIDDAY, **kwargs):
    fetcher = AsyncMock(return_value=html) if isinstance(html, bytes) else AsyncMock(side_effect=html)
    with patch("clear_outside_apy.client.fetch_html", fetcher):
        status, body, headers = asyncio.run(handle(method, BASE + path, **kwargs))
    return status, (json.loads(body) if body else None), headers, fetcher


def test_index():
    status, body, headers, fetcher = call("GET", "/")
    assert status == 200
    assert body["example"].startswith(BASE + "/forecast/")
    assert headers["Access-Control-Allow-Origin"] == "*"
    fetcher.assert_not_awaited()


def test_forecast_defaults():
    status, body, headers, fetcher = call("GET", "/forecast/43.16/-75.84", cache_ttl=300)
    assert status == 200
    assert body["url"] == "https://clearoutside.com/forecast/43.16/-75.84?view=midday"
    assert body["units"]["visibility"] == "km"
    assert len(body["forecast"]) == 7
    assert headers["Content-Type"].startswith("application/json")
    assert headers["Cache-Control"] == "public, max-age=300"
    assert fetcher.await_args.kwargs["cache_ttl"] == 300


def test_forecast_query_options():
    status, body, _, fetcher = call(
        "GET", "/forecast/43.164/-75.841/?view=current&experimental=1&units=imperial"
    )
    assert status == 200
    assert fetcher.await_args.args[0] == (
        "https://clearoutside.com/forecast/43.16/-75.84?view=current&experimental=on"
    )
    assert body["view"] == "current"
    assert body["experimental"] is True
    assert body["units"]["visibility"] == "miles"


@pytest.mark.parametrize(
    "path",
    [
        "/forecast/100/0",
        "/forecast/abc/0",
        "/forecast/0/0?view=noon",
        "/forecast/0/0?units=furlongs",
        "/forecast/0/0?experimental=maybe",
    ],
)
def test_bad_requests(path):
    status, body, headers, fetcher = call("GET", path)
    assert status == 400
    assert body["error"]["message"]
    assert headers["Cache-Control"] == "no-store"
    fetcher.assert_not_awaited()


def test_upstream_failures_are_502():
    status, body, _, _ = call("GET", "/forecast/0/0", html=FetchError("HTTP 503"))
    assert status == 502
    assert body["error"]["type"] == "FetchError"
    status, body, _, _ = call("GET", "/forecast/0/0", html=b"<html>nope</html>")
    assert status == 502
    assert body["error"]["type"] == "ParseError"


def test_not_found_and_methods():
    assert call("GET", "/nope")[0] == 404
    assert call("GET", "/forecast/1")[0] == 404
    status, _, headers, _ = call("POST", "/forecast/0/0")
    assert status == 405
    assert headers["Allow"] == "GET, OPTIONS"
    status, body, headers, _ = call("OPTIONS", "/forecast/0/0")
    assert status == 204
    assert body is None
    assert "GET" in headers["Access-Control-Allow-Methods"]


def test_cache_disabled():
    _, _, headers, _ = call("GET", "/forecast/43.16/-75.84", cache_ttl=0)
    assert headers["Cache-Control"] == "no-store"
