"""Booking – links a Passenger to a seat on a Flight."""

from datetime import timedelta

from ..enums import BookingStatus, FlightClass, FlightStatus, InsuranceTier
from ..errors import CheckInError, InvalidDataError
from ..utils import now as clock_now, timestamp


class Booking:
    CHECK_IN_OPENS_HOURS = 24
    CHECK_IN_CLOSES_HOURS = 0.75   # 45 minutes before departure

    def __init__(
        self,
        booking_id,
        passenger,
        flight,
        flight_class,
        seat,
        insurance=InsuranceTier.NONE.value,
        insurance_cost=0,
        status=BookingStatus.CONFIRMED.value,
        created_at=None,
        ticket_price=None,
        payment_ref=None,
        card_last4=None,
        miles_earned=0,
        checked_in_at=None,
        boarding_group=None,
        cancelled_at=None,
        refund_amount=0,
        fare_breakdown=None,
        extra_bags=0,
        baggage_fee=0,
    ):
        self.booking_id = booking_id
        self.passenger = passenger
        self.flight = flight
        self.flight_class = flight_class.value if isinstance(flight_class, FlightClass) else flight_class
        self.seat = seat
        self.insurance = insurance
        self.insurance_cost = float(insurance_cost)
        self.status = status
        self.created_at = created_at or timestamp()
        # Fare is frozen at purchase time – dynamic prices move afterwards.
        self._ticket_price = float(ticket_price) if ticket_price is not None else None
        self.payment_ref = payment_ref
        self.card_last4 = card_last4
        self.miles_earned = int(miles_earned or 0)
        self.checked_in_at = checked_in_at
        self.boarding_group = boarding_group
        self.cancelled_at = cancelled_at
        self.refund_amount = float(refund_amount or 0)
        self.fare_breakdown = fare_breakdown or {}
        self.extra_bags = int(extra_bags or 0)        # checked bags bought on top of the allowance
        self.baggage_fee = float(baggage_fee or 0)

    # ---- money --------------------------------------------------------------
    @property
    def ticket_price(self):
        if self._ticket_price is not None:
            return self._ticket_price
        return self.flight.class_price(self.flight_class)   # legacy records

    @property
    def total_cost(self):
        return self.ticket_price + self.insurance_cost + self.baggage_fee

    @property
    def refundable_base(self):
        """What refund percentages apply to: fare + bag fees (cover is never refunded)."""
        return self.ticket_price + self.baggage_fee

    @property
    def included_bags(self):
        return self.flight.carrier.baggage.included_bags(self.flight_class)

    @property
    def total_bags(self):
        return self.included_bags + self.extra_bags

    @property
    def net_revenue(self):
        """What the airline keeps: full total, or total minus refund if cancelled."""
        if self.status == BookingStatus.CANCELLED.value:
            return max(0.0, self.total_cost - self.refund_amount)
        return self.total_cost

    # ---- lifecycle ----------------------------------------------------------
    @property
    def is_active(self):
        return self.status in (BookingStatus.CONFIRMED.value, BookingStatus.CHECKED_IN.value)

    def display_status(self, moment=None):
        if self.is_active and self.flight.status(moment) == FlightStatus.LANDED:
            return BookingStatus.FLOWN.value
        if self.is_active and self.flight.status(moment) == FlightStatus.CANCELLED:
            return "Flight cancelled"
        return self.status

    def check_in_window(self, moment=None):
        """Return (is_open, message) explaining the online check-in state."""
        moment = moment or clock_now()
        if not self.is_active:
            return False, "This booking is cancelled."
        if self.status == BookingStatus.CHECKED_IN.value:
            return False, "You're already checked in."
        if self.flight.status(moment) == FlightStatus.CANCELLED:
            return False, "This flight was cancelled."
        hours = self.flight.hours_until_departure(moment)
        if hours > self.CHECK_IN_OPENS_HOURS:
            return False, f"Check-in opens 24 hours before departure ({hours - 24:.0f}h from now)."
        if hours < self.CHECK_IN_CLOSES_HOURS:
            return False, "Online check-in has closed for this flight."
        return True, "Check-in is open."

    def check_in(self, moment=None):
        is_open, message = self.check_in_window(moment)
        if not is_open:
            raise CheckInError(message)
        self.status = BookingStatus.CHECKED_IN.value
        self.checked_in_at = timestamp(moment)
        self.boarding_group = self._boarding_group()

    def _boarding_group(self):
        cabin = FlightClass.parse(self.flight_class)
        if cabin == FlightClass.FIRST:
            return 1
        if cabin == FlightClass.BUSINESS:
            return 2
        # Economy boards back-to-front in three groups.
        row = self.flight.seat_row(self.seat)
        rows = self.flight.row_count
        return 3 if row > rows * 2 / 3 else 4 if row > rows / 3 else 5

    def mark_cancelled(self, refund_amount, moment=None):
        if not self.is_active:
            raise InvalidDataError("Booking is already cancelled.")
        self.status = BookingStatus.CANCELLED.value
        self.cancelled_at = timestamp(moment)
        self.refund_amount = float(refund_amount)

    @property
    def gate_closes_at(self):
        return self.flight.expected_departure_dt - timedelta(minutes=20)

    @property
    def lead_days(self):
        """Days between purchase and departure – a classic demand feature."""
        from ..utils import parse_datetime
        delta = self.flight.departure_dt - parse_datetime(self.created_at)
        return max(0.0, delta.total_seconds() / 86400)

    # ---- serialisation ------------------------------------------------------
    def to_dict(self):
        return {
            "id": self.booking_id,
            "passport": self.passenger.passport,
            "flight_number": self.flight.number,
            "flight_class": self.flight_class,
            "seat": self.seat,
            "insurance": self.insurance,
            "insurance_cost": self.insurance_cost,
            "ticket_price": self.ticket_price,
            "total_cost": self.total_cost,
            "status": self.status,
            "created_at": self.created_at,
            "payment_ref": self.payment_ref,
            "card_last4": self.card_last4,
            "miles_earned": self.miles_earned,
            "checked_in_at": self.checked_in_at,
            "boarding_group": self.boarding_group,
            "cancelled_at": self.cancelled_at,
            "refund_amount": self.refund_amount,
            "fare_breakdown": self.fare_breakdown,
            "extra_bags": self.extra_bags,
            "baggage_fee": self.baggage_fee,
        }

    @classmethod
    def from_dict(cls, data, passenger, flight):
        return cls(
            booking_id=data.get("id", data.get("booking_id")),
            passenger=passenger,
            flight=flight,
            flight_class=data.get("flight_class", FlightClass.ECONOMY.value),
            seat=data.get("seat", ""),
            insurance=data.get("insurance", InsuranceTier.NONE.value),
            insurance_cost=float(data.get("insurance_cost", 0)),
            status=data.get("status", BookingStatus.CONFIRMED.value),
            created_at=data.get("created_at") or timestamp(),
            ticket_price=data.get("ticket_price"),
            payment_ref=data.get("payment_ref"),
            card_last4=data.get("card_last4"),
            miles_earned=data.get("miles_earned", 0),
            checked_in_at=data.get("checked_in_at"),
            boarding_group=data.get("boarding_group"),
            cancelled_at=data.get("cancelled_at"),
            refund_amount=data.get("refund_amount", 0),
            fare_breakdown=data.get("fare_breakdown"),
            extra_bags=data.get("extra_bags", 0),
            baggage_fee=data.get("baggage_fee", 0),
        )

    def __repr__(self):
        return f"Booking({self.booking_id}, {self.flight.number}, {self.seat}, {self.status})"
