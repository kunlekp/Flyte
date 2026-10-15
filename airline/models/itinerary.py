"""Itinerary – a trip made of one or more flights booked and paid together.

A one-way trip has one leg, a return trip two (out and back), and a
multi-city trip two to four. Each leg is an ordinary Booking; the Itinerary
groups them and answers questions about the whole journey.
"""

from ..enums import TripType


class Itinerary:
    def __init__(self, trip_id, trip_type, bookings):
        self.trip_id = trip_id
        self.trip_type = TripType.parse(trip_type)
        self.bookings = sorted(bookings, key=lambda b: (b.leg_index, b.flight.departure))

    # ---- the journey --------------------------------------------------------
    @property
    def legs(self):
        return self.bookings

    @property
    def leg_count(self):
        return len(self.bookings)

    @property
    def passenger(self):
        return self.bookings[0].passenger

    @property
    def cities(self):
        """['Lagos', 'Abuja', 'Lagos'] – every stop in order."""
        stops = [self.bookings[0].flight.origin]
        for b in self.bookings:
            if b.flight.origin != stops[-1]:      # open-jaw: a gap you travel by other means
                stops.append(b.flight.origin)
            stops.append(b.flight.destination)
        return stops

    @property
    def route_label(self):
        return " → ".join(self.cities)

    @property
    def first_departure(self):
        return self.bookings[0].flight.departure

    @property
    def last_arrival(self):
        return self.bookings[-1].flight.arrival

    # ---- money --------------------------------------------------------------
    @property
    def fares(self):
        return sum(b.ticket_price for b in self.bookings)

    @property
    def discount(self):
        """₦ saved by booking the legs together (return trips)."""
        return sum(float(b.fare_breakdown.get("trip_discount", 0) or 0) for b in self.bookings)

    @property
    def baggage_fees(self):
        return sum(b.baggage_fee for b in self.bookings)

    @property
    def insurance_cost(self):
        return sum(b.insurance_cost for b in self.bookings)

    @property
    def total_cost(self):
        return sum(b.total_cost for b in self.bookings)

    @property
    def refunded(self):
        return sum(b.refund_amount for b in self.bookings)

    # ---- status -------------------------------------------------------------
    @property
    def is_active(self):
        return any(b.is_active for b in self.bookings)

    @property
    def active_legs(self):
        return [b for b in self.bookings if b.is_active]

    def to_dict(self):
        return {
            "trip_id": self.trip_id,
            "trip_type": self.trip_type.value,
            "route": self.route_label,
            "legs": [b.booking_id for b in self.bookings],
            "total_cost": self.total_cost,
        }

    def __repr__(self):
        return f"Itinerary({self.trip_id}, {self.trip_type.value}, {self.route_label})"
