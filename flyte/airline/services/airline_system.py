"""AirlineSystem – the application service that owns all domain objects.

Same public API as the console project (save, load, add_flight, remove_flight,
get_flight, search_flights, register_passenger, get_passenger, create_booking,
get_booking, cancel_booking, add_sample_flights) plus the extra operations a
real product needs: accounts, payments, dynamic pricing, check-in, flight
disruption handling and refunds.

Collaborators are injected (dependency injection), so tests and the web app
can swap storage, payment gateway or notifier without touching this class.
"""

import threading
from datetime import timedelta

from ..enums import BookingStatus, FlightClass, FlightStatus, InsuranceTier, Role
from ..errors import (
    AuthError, BookingNotFoundError, CabinMismatchError, DuplicateError, FlightFullError,
    FlightNotBookableError, InvalidDataError, SeatNotFoundError, SeatOccupiedError,
)
from ..models import Booking, Flight, Passenger, User
from ..utils import email_valid, format_datetime, now as clock_now, parse_datetime, timestamp
from .notifier import LogNotifier, NotificationService
from .payments import MockPaymentGateway
from .pricing import FareAdvisor, LoyaltyProgram, PricingEngine, RefundPolicy
from .storage import JsonStorage


class AirlineSystem:
    def __init__(
        self,
        database="airline_db.json",
        *,
        storage=None,
        pricing=None,
        payments=None,
        notifications=None,
        refund_policy=None,
        loyalty=None,
    ):
        self.database = database
        self.storage = storage or JsonStorage(database)
        self.pricing = pricing or PricingEngine()
        self.advisor = FareAdvisor(self.pricing)
        self.payments = payments or MockPaymentGateway()
        self.notifications = notifications or NotificationService(LogNotifier())
        self.refund_policy = refund_policy or RefundPolicy()
        self.loyalty = loyalty or LoyaltyProgram()

        self.flights = {}
        self.passengers = {}
        self.bookings = {}
        self.users = {}
        self.booking_number = 1000
        self.lock = threading.RLock()

    # =========================================================================
    # DATABASE
    # =========================================================================
    def _persist(self, collection, key, obj):
        self.storage.upsert(collection, key, obj.to_dict())

    def save(self):
        """Write everything (kept for the console UI and migrations)."""
        with self.lock, self.storage.batch():
            self.storage.set_meta("booking_number", self.booking_number)
            for number, flight in self.flights.items():
                self._persist("flights", number, flight)
            for passport, passenger in self.passengers.items():
                self._persist("passengers", passport, passenger)
            for booking_id, booking in self.bookings.items():
                self._persist("bookings", booking_id, booking)
            for email, user in self.users.items():
                self._persist("users", email, user)

    @staticmethod
    def _normalise(collection, id_keys):
        """Old console databases stored collections as lists – convert."""
        if isinstance(collection, list):
            out = {}
            for item in collection:
                if not isinstance(item, dict):
                    continue
                key = next((item.get(k) for k in id_keys if item.get(k)), None)
                if key:
                    out[str(key)] = item
            return out
        return collection if isinstance(collection, dict) else {}

    def load(self):
        snapshot = self.storage.load()
        self.load_snapshot(snapshot)

    def load_snapshot(self, snapshot):
        with self.lock:
            meta = snapshot.get("meta", {})
            self.booking_number = int(meta.get("booking_number", snapshot.get("booking_number", 1000)))

            flights = self._normalise(snapshot.get("flights", {}), ("number", "flight_number"))
            passengers = self._normalise(snapshot.get("passengers", {}), ("passport",))
            bookings = self._normalise(snapshot.get("bookings", {}), ("id", "booking_id"))
            users = self._normalise(snapshot.get("users", {}), ("email",))

            self.flights = {}
            for value in flights.values():
                try:
                    flight = Flight.from_dict(value)
                    self.flights[flight.number] = flight
                except (ValueError, TypeError, KeyError):
                    continue

            self.passengers = {}
            for value in passengers.values():
                try:
                    passenger = Passenger.from_dict(value)
                    self.passengers[passenger.passport] = passenger
                except (ValueError, TypeError, KeyError):
                    continue

            self.bookings = {}
            for key, value in bookings.items():
                try:
                    passport = str(value.get("passport", value.get("passenger_passport", ""))).upper()
                    flight_number = str(value.get("flight_number", value.get("flight", ""))).upper()
                    passenger = self.passengers.get(passport)
                    flight = self.flights.get(flight_number)
                    if not passenger or not flight:
                        continue
                    value.setdefault("id", key)
                    booking = Booking.from_dict(value, passenger, flight)
                    self.bookings[booking.booking_id] = booking
                    if booking.is_active and booking.seat in flight.seats:
                        flight.seats[booking.seat] = passenger.passport   # keep seats consistent
                except (ValueError, TypeError, KeyError):
                    continue

            self.users = {}
            for value in users.values():
                try:
                    user = User.from_dict(value)
                    self.users[user.email] = user
                except (ValueError, TypeError, KeyError):
                    continue

    # =========================================================================
    # FLIGHTS
    # =========================================================================
    def add_flight(self, flight):
        with self.lock:
            if flight.number in self.flights:
                raise DuplicateError("Flight already exists.")
            flight.validate()
            flight.created_at = flight.created_at or timestamp()
            self.flights[flight.number] = flight
            self._persist("flights", flight.number, flight)
        return flight

    def update_flight(self, number, **changes):
        """Edit schedule / fare. Capacity is fixed once seats exist."""
        with self.lock:
            flight = self.get_flight(number)
            fields = ("origin", "destination", "departure", "arrival", "aircraft_type", "airline", "price")
            backup = {name: getattr(flight, name) for name in fields}
            for field in ("origin", "destination", "departure", "arrival", "aircraft_type", "airline"):
                if changes.get(field):
                    setattr(flight, field, changes[field])
            if changes.get("price") not in (None, ""):
                flight.price = float(changes["price"])
            try:
                flight.validate()
            except InvalidDataError:
                for name, value in backup.items():   # roll back in place
                    setattr(flight, name, value)
                raise
            self._persist("flights", flight.number, flight)
            return flight

    def remove_flight(self, number):
        with self.lock:
            number = number.upper()
            if number not in self.flights:
                raise InvalidDataError("Flight not found.")
            active = [b for b in self.bookings.values() if b.flight.number == number and b.is_active]
            if active:
                raise InvalidDataError("Cannot remove a flight with active bookings. Cancel the flight instead.")
            for booking_id in [k for k, b in self.bookings.items() if b.flight.number == number]:
                del self.bookings[booking_id]
                self.storage.delete("bookings", booking_id)
            del self.flights[number]
            self.storage.delete("flights", number)

    def get_flight(self, number):
        number = (number or "").upper()
        if number not in self.flights:
            raise InvalidDataError("Flight not found.")
        return self.flights[number]

    def search_flights(self, keyword=None, *, origin=None, destination=None,
                       departure_date=None, airline=None, bookable_only=False, moment=None):
        if all(v is None for v in (origin, destination, departure_date, airline)):
            keyword = (keyword or "").lower()
            results = [
                f for f in self.flights.values()
                if keyword in f.number.lower() or keyword in f.origin.lower() or keyword in f.destination.lower()
            ]
        else:
            results = []
            for flight in self.flights.values():
                if departure_date and flight.departure[:10] != departure_date:
                    continue
                if origin and not self._place_matches(origin, flight.origin, flight.origin_code):
                    continue
                if destination and not self._place_matches(destination, flight.destination, flight.destination_code):
                    continue
                if airline and airline.casefold() not in flight.airline.casefold():
                    continue
                results.append(flight)
        if bookable_only:
            results = [f for f in results if f.is_bookable(moment)]
        return sorted(results, key=lambda f: f.departure)

    @staticmethod
    def _place_matches(query, city, code):
        query = query.strip().casefold()
        if "(" in query and query.endswith(")"):        # "Lagos (LOS)"
            query = query[:query.rindex("(")].strip()
        return query in city.casefold() or query == code.casefold()

    def upcoming_flights(self, moment=None, limit=None):
        moment = moment or clock_now()
        flights = sorted((f for f in self.flights.values() if f.is_bookable(moment)), key=lambda f: f.departure)
        return flights[:limit] if limit else flights

    def delay_flight(self, number, minutes):
        with self.lock:
            flight = self.get_flight(number)
            if minutes < 0 or minutes > 24 * 60:
                raise InvalidDataError("Delay must be between 0 and 1440 minutes.")
            flight.delay_minutes = int(minutes)
            flight.manual_status = FlightStatus.DELAYED.value if minutes else None
            self._persist("flights", flight.number, flight)
            if minutes:
                for booking in self.bookings_for_flight(flight.number, active_only=True):
                    self.notifications.flight_disrupted(
                        booking, f"Delayed by {minutes} min – new departure {format_datetime(flight.expected_departure_dt)}.")
            return flight

    def cancel_flight(self, number, moment=None):
        """Airline-initiated cancellation: every active booking is refunded in full."""
        with self.lock:
            flight = self.get_flight(number)
            refunded = 0
            for booking in self.bookings_for_flight(flight.number, active_only=True):
                self._cancel(booking, moment, airline_cancelled=True)
                refunded += 1
            flight.manual_status = FlightStatus.CANCELLED.value
            self._persist("flights", flight.number, flight)
            return refunded

    # =========================================================================
    # PASSENGERS & USERS
    # =========================================================================
    def register_passenger(self, passenger):
        with self.lock:
            if passenger.passport in self.passengers:
                raise DuplicateError("Passenger already exists.")
            self.passengers[passenger.passport] = passenger
            self._persist("passengers", passenger.passport, passenger)
        return passenger

    def get_passenger(self, passport):
        passport = (passport or "").upper()
        if passport not in self.passengers:
            raise InvalidDataError("Passenger not found.")
        return self.passengers[passport]

    def update_passenger(self, passport, **changes):
        with self.lock:
            passenger = self.get_passenger(passport)
            if "email" in changes and not email_valid(changes["email"]):
                raise InvalidDataError("Enter a valid email address.")
            for field in ("name", "phone", "email"):
                if changes.get(field):
                    setattr(passenger, field, changes[field].strip())
            if changes.get("age"):
                passenger.age = int(changes["age"])
            self._persist("passengers", passenger.passport, passenger)
            return passenger

    def register_user(self, email, password, *, name, passport, age, phone, role=Role.PASSENGER.value):
        email = (email or "").strip().lower()
        passport = (passport or "").strip().upper()
        if not email_valid(email):
            raise InvalidDataError("Enter a valid email address.")
        with self.lock:
            if email in self.users:
                raise DuplicateError("An account with that email already exists. Log in instead.")
            existing = self.passengers.get(passport)
            if existing and existing.email.lower() != email:
                raise DuplicateError("That passport is registered to another email.")
            if any(u.passport == passport for u in self.users.values()):
                raise DuplicateError("That passport already has an account.")
            user = User.create(email, password, role=role, passport=passport, display_name=name)
            if not existing:
                self.register_passenger(Passenger(passport, name, age, phone, email))
            self.users[email] = user
            self._persist("users", email, user)
            return user

    def create_admin(self, email, password, name="Admin"):
        email = email.strip().lower()
        with self.lock:
            if email in self.users:
                return self.users[email]
            user = User.create(email, password, role=Role.ADMIN.value, display_name=name)
            self.users[email] = user
            self._persist("users", email, user)
            return user

    def authenticate(self, email, password):
        user = self.users.get((email or "").strip().lower())
        if not user or not user.verify_password(password):
            raise AuthError("That email and password don't match.")
        user.last_login = timestamp()
        self._persist("users", user.email, user)
        return user

    def get_user(self, email):
        return self.users.get((email or "").lower())

    # =========================================================================
    # PRICING
    # =========================================================================
    def quote(self, flight_number, flight_class, insurance=InsuranceTier.NONE, moment=None, extra_bags=0):
        flight = self.get_flight(flight_number)
        return (self.pricing.quote(flight, flight_class, moment)
                .with_insurance(insurance)
                .with_baggage(flight.carrier.baggage, extra_bags))

    def booking_velocity(self, flight_number, days=7, moment=None):
        """Average bookings/day for a flight over the last `days` days."""
        moment = moment or clock_now()
        since = moment - timedelta(days=days)
        count = sum(
            1 for b in self.bookings.values()
            if b.flight.number == flight_number and parse_datetime(b.created_at) >= since
        )
        return count / days

    def booking_velocities(self, days=7, moment=None):
        """{flight_number: bookings/day} for every flight in one pass."""
        moment = moment or clock_now()
        since = timestamp(moment - timedelta(days=days))
        counts = {}
        for booking in self.bookings.values():
            if booking.created_at >= since:            # ISO strings sort chronologically
                counts[booking.flight.number] = counts.get(booking.flight.number, 0) + 1
        return {number: count / days for number, count in counts.items()}

    def fare_advice(self, flight_number, flight_class=FlightClass.ECONOMY, moment=None, velocity=None):
        flight = self.get_flight(flight_number)
        if velocity is None:
            velocity = self.booking_velocity(flight.number, moment=moment)
        return self.advisor.advise(flight, flight_class, velocity, moment)

    # =========================================================================
    # BOOKINGS
    # =========================================================================
    def _validate_seat(self, flight, seat, cabin):
        if flight.is_full():
            raise FlightFullError("This flight is full.")
        if seat not in flight.seats:
            raise SeatNotFoundError(f"Seat {seat} does not exist.")
        if flight.seats[seat] is not None:
            raise SeatOccupiedError(f"Seat {seat} was just taken. Pick another seat.")
        if flight.cabin_for_seat(seat) != cabin:
            raise CabinMismatchError(f"Seat {seat} is in {flight.cabin_for_seat(seat).value}, not {cabin.value}.")

    def create_booking(self, passport, flight_number, flight_class, seat, insurance,
                       insurance_cost=None, *, payment_ref=None, card_last4=None, moment=None,
                       enforce_schedule=True, quote=None, extra_bags=0):
        """Reserve a seat and create the booking record.

        ``insurance_cost`` is accepted for backwards compatibility with the
        console UI, but the price always comes from InsuranceTier (server
        side) so a client cannot under-pay.
        """
        with self.lock:
            passenger = self.get_passenger(passport)
            flight = self.get_flight(flight_number)
            cabin = FlightClass.parse(flight_class)
            tier = InsuranceTier.parse(insurance)
            seat = (seat or "").upper()
            if enforce_schedule and not flight.is_bookable(moment):
                raise FlightNotBookableError("This flight is no longer open for booking.")
            self._validate_seat(flight, seat, cabin)
            baggage_fee = flight.carrier.baggage.fee_for(extra_bags)   # validates 0..3 too

            quote = quote or self.pricing.quote(flight, cabin, moment)
            self.booking_number += 1
            booking_id = f"BK{self.booking_number}"
            flight.reserve(seat, passenger.passport)

            miles = self.loyalty.miles_for(flight.distance_km, cabin, passenger.loyalty_tier)
            booking = Booking(
                booking_id=booking_id,
                passenger=passenger,
                flight=flight,
                flight_class=cabin,
                seat=seat,
                insurance=tier.value,
                insurance_cost=tier.price,
                ticket_price=quote.fare,
                payment_ref=payment_ref,
                card_last4=card_last4,
                miles_earned=miles,
                created_at=timestamp(moment),
                fare_breakdown={
                    "list_price": quote.list_price,
                    "demand_multiplier": quote.demand_multiplier,
                    "time_multiplier": quote.time_multiplier,
                    "airline": flight.carrier.code,
                },
                extra_bags=extra_bags,
                baggage_fee=baggage_fee,
            )
            self.bookings[booking_id] = booking
            passenger.add_booking(booking_id)
            passenger.earn_miles(miles)

            with self.storage.batch():
                self.storage.set_meta("booking_number", self.booking_number)
                self._persist("bookings", booking_id, booking)
                self._persist("flights", flight.number, flight)
                self._persist("passengers", passenger.passport, passenger)
            return booking

    def book_and_pay(self, passport, flight_number, flight_class, seat, insurance, card, moment=None, extra_bags=0):
        """Full checkout: validate → price → charge card → create booking → email."""
        with self.lock:
            flight = self.get_flight(flight_number)
            cabin = FlightClass.parse(flight_class)
            if not flight.is_bookable(moment):
                raise FlightNotBookableError("This flight is no longer open for booking.")
            self._validate_seat(flight, (seat or "").upper(), cabin)
            quote = (self.pricing.quote(flight, cabin, moment)
                     .with_insurance(insurance)
                     .with_baggage(flight.carrier.baggage, extra_bags))
            payment = self.payments.charge(quote.total, card, f"{flight.number} {seat}")
            booking = self.create_booking(
                passport, flight_number, cabin, seat, insurance,
                payment_ref=payment.reference, card_last4=payment.last4, moment=moment, quote=quote,
                extra_bags=extra_bags,
            )
        self.notifications.booking_confirmed(booking)
        return booking

    def get_booking(self, booking_id):
        booking_id = (booking_id or "").strip().upper()
        if booking_id not in self.bookings:
            raise BookingNotFoundError("Booking not found.")
        return self.bookings[booking_id]

    def find_booking(self, booking_id, email):
        """Guest lookup – needs both the reference and the passenger email."""
        try:
            booking = self.get_booking(booking_id)
        except BookingNotFoundError:
            booking = None
        if not booking or booking.passenger.email.lower() != (email or "").strip().lower():
            raise BookingNotFoundError("No booking matches that reference and email.")
        return booking

    def bookings_for(self, passport):
        passport = (passport or "").upper()
        return sorted((b for b in self.bookings.values() if b.passenger.passport == passport),
                      key=lambda b: b.flight.departure, reverse=True)

    def bookings_for_flight(self, flight_number, active_only=False):
        return [b for b in self.bookings.values()
                if b.flight.number == flight_number and (b.is_active or not active_only)]

    def refund_preview(self, booking_id, moment=None):
        booking = self.get_booking(booking_id)
        return self.refund_policy.refund_for(booking, moment)

    def _cancel(self, booking, moment=None, airline_cancelled=False):
        amount, note = self.refund_policy.refund_for(booking, moment, airline_cancelled)
        if booking.flight.seats.get(booking.seat) == booking.passenger.passport:
            booking.flight.release(booking.seat)
        booking.mark_cancelled(round(amount, 2), moment)
        booking.passenger.revoke_miles(booking.miles_earned)
        if amount > 0 and booking.payment_ref:
            self.payments.refund(booking.payment_ref, amount)
        with self.storage.batch():
            self._persist("bookings", booking.booking_id, booking)
            self._persist("flights", booking.flight.number, booking.flight)
            self._persist("passengers", booking.passenger.passport, booking.passenger)
        self.notifications.booking_cancelled(booking, note)
        return note

    def cancel_booking(self, booking_id, moment=None):
        with self.lock:
            booking = self.get_booking(booking_id)
            if booking.status == BookingStatus.CANCELLED.value:
                raise InvalidDataError("Booking is already cancelled.")
            if booking.flight.hours_until_departure(moment) <= 0:
                raise InvalidDataError("This flight has already departed.")
            return self._cancel(booking, moment)

    def check_in(self, booking_id, moment=None):
        with self.lock:
            booking = self.get_booking(booking_id)
            booking.check_in(moment)
            self._persist("bookings", booking.booking_id, booking)
        self.notifications.checked_in(booking)
        return booking

    # =========================================================================
    # SAMPLE DATA
    # =========================================================================
    def add_sample_flights(self, moment=None):
        """The five original sample flights, re-dated to the coming days."""
        if self.flights:
            return
        moment = (moment or clock_now()).replace(minute=0, second=0, microsecond=0)
        rows = [
            ("NG101", "Lagos", "Abuja", 1, 8, 75, 85000, 120, "Boeing 737"),
            ("NG202", "Abuja", "Lagos", 1, 11, 75, 85000, 120, "Boeing 737"),
            ("NG303", "Lagos", "Port Harcourt", 2, 9, 75, 75000, 100, "Airbus A320"),
            ("NG404", "Port Harcourt", "Lagos", 2, 14, 75, 75000, 100, "Airbus A320"),
            ("NG505", "Lagos", "Kano", 3, 7, 90, 95000, 150, "Boeing 737"),
        ]
        with self.storage.batch():
            for number, origin, dest, day, hour, minutes, price, capacity, aircraft in rows:
                dep = (moment + timedelta(days=day)).replace(hour=hour, minute=0)
                self.add_flight(Flight(number, origin, dest, format_datetime(dep),
                                       format_datetime(dep + timedelta(minutes=minutes)), price, capacity, aircraft))
