"""Web scraper / parser for clearoutside.com astronomy weather forecasts."""

from .client import (
    BASE_URL,
    VIEWS,
    ClearOutsideAPY,
    build_url,
    fetch_forecast,
    parse,
)
from .exceptions import (
    ClearOutsideError,
    FetchError,
    InvalidLocationError,
    ParseError,
)

__version__ = "2.0.0"
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
    "__version__",
]
