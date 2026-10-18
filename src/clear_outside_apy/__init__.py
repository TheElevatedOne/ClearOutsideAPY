"""clearoutside.com forecast scraper for Cloudflare Python Workers."""

from .client import (
    BASE_URL,
    VIEWS,
    ClearOutsideAPY,
    build_url,
    fetch_forecast,
    fetch_html,
    parse,
)
from .exceptions import (
    ClearOutsideError,
    FetchError,
    InvalidLocationError,
    ParseError,
)

__version__ = "3.0.0"
__all__ = [
    "BASE_URL",
    "VIEWS",
    "ClearOutsideAPY",
    "ClearOutsideError",
    "build_url",
    "parse",
    "FetchError",
    "InvalidLocationError",
    "ParseError",
    "fetch_forecast",
    "fetch_html",
    "__version__",
]
