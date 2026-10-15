"""Custom exception hierarchy.

Every domain error inherits from ``AirlineError`` (same as the original
console project) so callers can catch one base class. The web layer maps
these to friendly messages and HTTP status codes via ``http_status``.
"""


class AirlineError(Exception):
    """Base class for every expected, user-facing domain error."""

    http_status = 400

    def __init__(self, message="Something went wrong with that request."):
        super().__init__(message)
        self.message = message


class FlightFullError(AirlineError):
    http_status = 409


class BookingNotFoundError(AirlineError):
    http_status = 404


class DuplicateError(AirlineError):
    http_status = 409


class InvalidDataError(AirlineError):
    pass


class SeatOccupiedError(AirlineError):
    http_status = 409


class SeatNotFoundError(AirlineError):
    http_status = 404


# ---- new for the web version ------------------------------------------------

class CabinMismatchError(AirlineError):
    """Seat chosen is not in the cabin (class) that was paid for."""


class CheckInError(AirlineError):
    """Check-in window closed, booking cancelled, etc."""


class PaymentError(AirlineError):
    http_status = 402


class AuthError(AirlineError):
    http_status = 401


class PermissionDeniedError(AirlineError):
    http_status = 403


class FlightNotBookableError(AirlineError):
    """Flight already departed, cancelled, or closed for sale."""
    http_status = 409
