"""Flight – schedule, seat inventory, cabins and live status."""

import math
from datetime import timedelta

from ..enums import FlightClass, FlightStatus
from ..errors import FlightFullError, SeatNotFoundError, SeatOccupiedError, InvalidDataError
from ..utils import parse_datetime, now as clock_now
from .airport import AIRPORTS
from .carrier import AIRLINES


class Flight:
    SEAT_COLUMNS = ["A", "B", "C", "D", "E", "F"]

    CLASS_MULTIPLIERS = {
        FlightClass.ECONOMY.value: 1.0,
        FlightClass.BUSINESS.value: 1.8,
        FlightClass.FIRST.value: 2.5,
    }

    BOARDING_WINDOW = timedelta(minutes=45)

    def __init__(
        self,
        number,
        origin,
        destination,
        departure,
        arrival,
        price,
        capacity=100,
        aircraft_type="Boeing 737",
        seats=None,
        airline="Independent carrier",
        first_rows=None,
        business_rows=None,
        manual_status=None,
        delay_minutes=0,
        created_at=None,
    ):
        self.number = number.upper()
        self.origin = origin
        self.destination = destination
        self.departure = departure
        self.arrival = arrival
        self.price = float(price)
        self.capacity = int(capacity)
        self.aircraft_type = aircraft_type
        self.airline = airline or "Independent carrier"
        self.manual_status = manual_status          # None | "Delayed" | "Cancelled"
        self.delay_minutes = int(delay_minutes or 0)
        self.created_at = created_at

        rows = self.row_count
        self.first_rows = int(first_rows) if first_rows is not None else (2 if rows >= 16 else 1 if rows >= 8 else 0)
        self.business_rows = int(business_rows) if business_rows is not None else max(1, round(rows * 0.15)) if rows >= 4 else 0

        self.seats = seats if seats is not None else self.create_seats()

    # ---- validation ---------------------------------------------------------
    def validate(self):
        if not self.origin or not self.destination:
            raise InvalidDataError("Origin and destination are required.")
        if self.origin.casefold() == self.destination.casefold():
            raise InvalidDataError("Origin and destination must be different.")
        if self.price <= 0:
            raise InvalidDataError("Base fare must be greater than zero.")
        if not 6 <= self.capacity <= 600:
            raise InvalidDataError("Capacity must be between 6 and 600 seats.")
        try:
            dep, arr = self.departure_dt, self.arrival_dt
        except ValueError as error:
            raise InvalidDataError(str(error)) from error
        if arr <= dep:
            raise InvalidDataError("Arrival must be after departure.")
        if self.first_rows + self.business_rows >= self.row_count:
            raise InvalidDataError("Leave at least one economy row.")

    # ---- seats --------------------------------------------------------------
    @property
    def row_count(self):
        return math.ceil(self.capacity / len(self.SEAT_COLUMNS))

    def create_seats(self):
        seats = {}
        columns = self.SEAT_COLUMNS
        for index in range(self.capacity):
            row = index // 6 + 1
            column = columns[index % 6]
            seats[f"{row}{column}"] = None
        return seats

    @staticmethod
    def seat_row(seat):
        digits = "".join(ch for ch in seat if ch.isdigit())
        return int(digits) if digits else 0

    def cabin_for_seat(self, seat):
        row = self.seat_row(seat)
        if row <= self.first_rows:
            return FlightClass.FIRST
        if row <= self.first_rows + self.business_rows:
            return FlightClass.BUSINESS
        return FlightClass.ECONOMY

    def available_seats(self, flight_class=None):
        cabin = FlightClass.parse(flight_class) if flight_class else None
        return [
            seat for seat, passenger in self.seats.items()
            if passenger is None and (cabin is None or self.cabin_for_seat(seat) == cabin)
        ]

    def available_count(self, flight_class=None):
        return len(self.available_seats(flight_class))

    def occupied_count(self):
        return sum(1 for value in self.seats.values() if value is not None)

    def is_full(self):
        return self.available_count() == 0

    def cabin_capacity(self, flight_class):
        cabin = FlightClass.parse(flight_class)
        return sum(1 for seat in self.seats if self.cabin_for_seat(seat) == cabin)

    @property
    def load_factor(self):
        """Share of seats sold, 0–1. The key airline health metric."""
        return self.occupied_count() / len(self.seats) if self.seats else 0.0

    def cabin_load_factor(self, flight_class):
        total = self.cabin_capacity(flight_class)
        if not total:
            return 0.0
        return 1 - self.available_count(flight_class) / total

    def seat_map(self):
        """Rows of seat dicts for the UI – never exposes who sits where."""
        rows = {}
        for seat, holder in self.seats.items():
            rows.setdefault(self.seat_row(seat), []).append({
                "seat": seat,
                "taken": holder is not None,
                "cabin": self.cabin_for_seat(seat).value,
            })
        return [{"row": row, "seats": seats} for row, seats in sorted(rows.items())]

    def reserve(self, seat, passport):
        if seat not in self.seats:
            raise SeatNotFoundError("Seat does not exist.")
        if self.seats[seat] is not None:
            raise SeatOccupiedError("That seat is already occupied.")
        if self.is_full():
            raise FlightFullError("This flight is full.")
        self.seats[seat] = passport

    def release(self, seat):
        if seat not in self.seats:
            raise SeatNotFoundError("Seat does not exist.")
        self.seats[seat] = None

    # ---- pricing ------------------------------------------------------------
    def class_price(self, flight_class):
        """Static list price (base × cabin multiplier). Dynamic pricing lives
        in services.pricing.PricingEngine and builds on top of this."""
        if isinstance(flight_class, FlightClass):
            flight_class = flight_class.value
        multiplier = self.CLASS_MULTIPLIERS.get(flight_class, 1.0)
        return self.price * multiplier

    # ---- time & geography ---------------------------------------------------
    @property
    def departure_dt(self):
        return parse_datetime(self.departure)

    @property
    def arrival_dt(self):
        return parse_datetime(self.arrival)

    @property
    def expected_departure_dt(self):
        return self.departure_dt + timedelta(minutes=self.delay_minutes)

    @property
    def duration_minutes(self):
        return int((self.arrival_dt - self.departure_dt).total_seconds() // 60)

    @property
    def duration_label(self):
        hours, minutes = divmod(self.duration_minutes, 60)
        return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"

    @property
    def carrier(self):
        """The Airline object operating this flight (its prices and bag rules)."""
        return AIRLINES.resolve(self.airline)

    @property
    def origin_airport(self):
        return AIRPORTS.find(self.origin)

    @property
    def destination_airport(self):
        return AIRPORTS.find(self.destination)

    @property
    def origin_code(self):
        airport = self.origin_airport
        return airport.code if airport else self.origin[:3].upper()

    @property
    def destination_code(self):
        airport = self.destination_airport
        return airport.code if airport else self.destination[:3].upper()

    @property
    def route(self):
        return f"{self.origin_code}–{self.destination_code}"

    @property
    def distance_km(self):
        distance = AIRPORTS.distance_km(self.origin, self.destination)
        # Unknown airport: estimate from block time at ~650 km/h cruise.
        return distance if distance is not None else max(150.0, self.duration_minutes * 650 / 60 * 0.8)

    def hours_until_departure(self, moment=None):
        moment = moment or clock_now()
        return (self.expected_departure_dt - moment).total_seconds() / 3600

    def status(self, moment=None):
        moment = moment or clock_now()
        if self.manual_status == FlightStatus.CANCELLED.value:
            return FlightStatus.CANCELLED
        dep = self.expected_departure_dt
        arr = self.arrival_dt + timedelta(minutes=self.delay_minutes)
        if moment >= arr:
            return FlightStatus.LANDED
        if moment >= dep:
            return FlightStatus.IN_AIR
        if moment >= dep - self.BOARDING_WINDOW:
            return FlightStatus.BOARDING
        if self.delay_minutes > 0 or self.manual_status == FlightStatus.DELAYED.value:
            return FlightStatus.DELAYED
        return FlightStatus.SCHEDULED

    def is_bookable(self, moment=None):
        """Sales close 2 hours before departure."""
        status = self.status(moment)
        if status in (FlightStatus.CANCELLED, FlightStatus.LANDED, FlightStatus.IN_AIR, FlightStatus.BOARDING):
            return False
        return self.hours_until_departure(moment) > 2 and not self.is_full()

    # ---- serialisation ------------------------------------------------------
    def to_dict(self):
        return {
            "number": self.number,
            "origin": self.origin,
            "destination": self.destination,
            "departure": self.departure,
            "arrival": self.arrival,
            "price": self.price,
            "capacity": self.capacity,
            "aircraft_type": self.aircraft_type,
            "airline": self.airline,
            "first_rows": self.first_rows,
            "business_rows": self.business_rows,
            "manual_status": self.manual_status,
            "delay_minutes": self.delay_minutes,
            "created_at": self.created_at,
            "seats": self.seats,
        }

    def summary(self, moment=None):
        """Lightweight public view used by JSON APIs and templates."""
        return {
            "number": self.number,
            "origin": self.origin,
            "destination": self.destination,
            "origin_code": self.origin_code,
            "destination_code": self.destination_code,
            "departure": self.departure,
            "arrival": self.arrival,
            "duration": self.duration_label,
            "aircraft_type": self.aircraft_type,
            "airline": self.carrier.name,
            "airline_code": self.carrier.code,
            "airline_colour": self.carrier.colour,
            "capacity": self.capacity,
            "seats_left": self.available_count(),
            "load_factor": round(self.load_factor, 4),
            "status": self.status(moment).value,
            "delay_minutes": self.delay_minutes,
            "distance_km": round(self.distance_km),
        }

    @classmethod
    def from_dict(cls, data):
        number = data.get("number", data.get("flight_number", ""))
        seats = data.get("seats")
        if not isinstance(seats, dict):     # support older databases
            seats = None
        flight = cls(
            number=number,
            origin=data.get("origin", ""),
            destination=data.get("destination", ""),
            departure=data.get("departure", ""),
            arrival=data.get("arrival", ""),
            price=float(data.get("price", data.get("base_price", 0))),
            capacity=int(data.get("capacity", 100)),
            aircraft_type=data.get("aircraft_type", data.get("aircraft", "Boeing 737")),
            seats=seats,
            airline=data.get("airline", data.get("carrier", "Independent carrier")),
            first_rows=data.get("first_rows"),
            business_rows=data.get("business_rows"),
            manual_status=data.get("manual_status"),
            delay_minutes=data.get("delay_minutes", 0),
            created_at=data.get("created_at"),
        )
        if isinstance(seats, dict):
            flight.seats = seats
        return flight

    def __repr__(self):
        return f"Flight({self.number} {self.route} {self.departure})"
