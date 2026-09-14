"""Exceptions raised by ClearOutsideAPY."""


class ClearOutsideError(Exception):
    """Base error for the Clear Outside client and parser."""


class ParseError(ClearOutsideError, ValueError):
    """The HTML is not a usable Clear Outside forecast page."""


class FetchError(ClearOutsideError):
    """The forecast page could not be downloaded."""


class InvalidLocationError(ClearOutsideError, ValueError):
    """Latitude, longitude, or view is invalid."""
