"""Async Clear Outside client for Cloudflare Python Workers."""

from __future__ import annotations

from typing import Any

from .exceptions import FetchError, InvalidLocationError
from .parser import parse_html as _parse_html

BASE_URL = "https://clearoutside.com/forecast/{lat}/{lon}"
VIEWS = ("midday", "midnight", "current")
DEFAULT_USER_AGENT = (
    "ClearOutsideAPY/3.0 (+https://github.com/TheElevatedOne/ClearOutsideAPY)"
)
DEFAULT_TIMEOUT = 20.0
# How long Cloudflare may cache the upstream page. The site regenerates
# forecasts a few times a day, so this mostly spares it repeat requests.
DEFAULT_UPSTREAM_TTL = 900


def _format_coord(value: float | int | str, name: str, lo: float, hi: float) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidLocationError(f"{name} must be a number, got {value!r}") from exc
    if not lo <= number <= hi:
        raise InvalidLocationError(f"{name} must be between {lo} and {hi}, got {number}")
    return f"{number:.2f}"


def _validate_view(view: str) -> str:
    if view not in VIEWS:
        allowed = ", ".join(VIEWS)
        raise InvalidLocationError(f"view must be one of: {allowed}")
    return view


def build_url(
    lat: float | int | str,
    lon: float | int | str,
    view: str = "midday",
    experimental: bool = False,
) -> str:
    """Return the Clear Outside forecast URL for a coordinate pair."""
    latitude = _format_coord(lat, "latitude", -90.0, 90.0)
    longitude = _format_coord(lon, "longitude", -180.0, 180.0)
    view = _validate_view(view)
    url = BASE_URL.format(lat=latitude, lon=longitude) + f"?view={view}"
    if experimental:
        url += "&experimental=on"
    return url


def parse(html: str | bytes, *, metric: bool = True) -> dict[str, Any]:
    """Parse a Clear Outside forecast HTML document into a dictionary."""
    if isinstance(html, str):
        payload = html.encode("utf-8")
    elif isinstance(html, (bytes, bytearray, memoryview)):
        payload = bytes(html)
    else:
        raise TypeError("html must be str or bytes")
    return _parse_html(payload, metric)


async def fetch_html(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str | None = None,
    cache_ttl: int = DEFAULT_UPSTREAM_TTL,
) -> bytes:
    """Download a forecast page with the Workers ``fetch`` API."""
    # Only importable inside the Workers runtime (Pyodide).
    from js import AbortSignal
    from workers import fetch

    options: dict[str, Any] = {
        "headers": {"User-Agent": user_agent or DEFAULT_USER_AGENT, "Accept": "text/html"},
        "signal": AbortSignal.timeout(int(timeout * 1000)),
    }
    if cache_ttl > 0:
        options["cf"] = {"cacheTtl": cache_ttl, "cacheEverything": True}
    try:
        response = await fetch(url, **options)
    except Exception as exc:  # JsException: DNS, TLS, abort/timeout, ...
        raise FetchError(f"failed to fetch {url}: {exc}") from exc
    if not response.ok:
        raise FetchError(f"HTTP {response.status} fetching {url}")
    return await response.bytes()


class ClearOutsideAPY:
    """Scrape and parse a 7-day hourly forecast from clearoutside.com.

    Parameters
    ----------
    lat, long:
        Latitude and longitude. Values are rounded to two decimal places,
        matching the website. ``lon`` is accepted as a keyword alias for
        ``long``.
    view:
        Hour alignment. ``midday`` starts at 12:00, ``midnight`` at 00:00,
        ``current`` at the current local hour.
    experimental:
        Request extra Met.no / 7Timer rows from the site.
    metric:
        Convert visibility, wind speed, and moon distance to kilometres.
        Temperatures stay in Celsius (that is how the site serves them).
    timeout, user_agent, cache_ttl:
        Upstream fetch settings. ``cache_ttl`` is how many seconds Cloudflare
        may cache the clearoutside.com page (0 disables it).

    Nothing is downloaded in ``__init__``; ``await pull()`` fetches the page
    on first use, and ``await update()`` downloads a fresh copy.
    """

    def __init__(
        self,
        lat: float | int | str,
        long: float | int | str | None = None,
        view: str = "midday",
        *,
        lon: float | int | str | None = None,
        experimental: bool = False,
        metric: bool = True,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str | None = None,
        cache_ttl: int = DEFAULT_UPSTREAM_TTL,
    ) -> None:
        if long is None and lon is None:
            raise TypeError("longitude is required (positional 'long' or keyword 'lon')")
        if long is not None and lon is not None:
            raise TypeError("give only one of 'long' or 'lon'")
        longitude = lon if long is None else long

        self.lat = _format_coord(lat, "latitude", -90.0, 90.0)
        self.long = _format_coord(longitude, "longitude", -180.0, 180.0)
        self.lon = self.long
        self.view = _validate_view(view)
        self.experimental = bool(experimental)
        self.metric = bool(metric)
        self.timeout = float(timeout)
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.cache_ttl = int(cache_ttl)
        self.url = build_url(
            self.lat, self.long, view=self.view, experimental=self.experimental
        )
        self.html: bytes | None = None

    async def update(self) -> None:
        """Download a fresh copy of the forecast page."""
        self.html = await fetch_html(
            self.url,
            timeout=self.timeout,
            user_agent=self.user_agent,
            cache_ttl=self.cache_ttl,
        )

    async def pull(self) -> dict[str, Any]:
        """Parse the downloaded HTML (fetching it first if needed)."""
        if self.html is None:
            await self.update()
        assert self.html is not None
        result = parse(self.html, metric=self.metric)
        result["url"] = self.url
        result["view"] = self.view
        result["experimental"] = self.experimental
        return result

    def __repr__(self) -> str:
        return (
            f"ClearOutsideAPY(lat={self.lat!r}, long={self.long!r}, "
            f"view={self.view!r}, experimental={self.experimental})"
        )


async def fetch_forecast(
    lat: float | int | str,
    long: float | int | str | None = None,
    view: str = "midday",
    *,
    lon: float | int | str | None = None,
    experimental: bool = False,
    metric: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str | None = None,
    cache_ttl: int = DEFAULT_UPSTREAM_TTL,
) -> dict[str, Any]:
    """One-shot helper: download and parse a forecast."""
    client = ClearOutsideAPY(
        lat,
        long,
        view,
        lon=lon,
        experimental=experimental,
        metric=metric,
        timeout=timeout,
        user_agent=user_agent,
        cache_ttl=cache_ttl,
    )
    return await client.pull()

