"""DemoDataSeeder – fills an empty database with ~3 months of realistic,
synthetic airline activity so the analytics have something to chew on.

Passengers are drawn from four behavioural personas; bookings arrive with
weekday/hour patterns and persona-specific lead times, and are priced by the
real PricingEngine at the moment they were "made". All names are fictional.
"""

import random
from datetime import timedelta

from .enums import FlightClass, InsuranceTier, TripType
from .models import AIRLINES, Flight, Passenger
from .services.notifier import Notifier, NotificationService
from .services.payments import CardDetails
from .utils import format_datetime, now as clock_now


class _NullNotifier(Notifier):
    def send(self, to, subject, body):
        pass


class Persona:
    def __init__(self, name, weight, trips, lead_mean, cabin_weights, insure, ages, extra_bag=0.2):
        self.name = name
        self.weight = weight
        self.trips = trips              # relative booking frequency
        self.lead_mean = lead_mean      # mean days booked ahead
        self.cabin_weights = cabin_weights
        self.insure = insure            # P(buys paid cover)
        self.ages = ages
        self.extra_bag = extra_bag      # P(buys an extra checked bag)


class DemoDataSeeder:
    FIRST_NAMES = ["Ada", "Chinedu", "Tolu", "Emeka", "Zainab", "Ifeoma", "Kunle", "Amaka", "Bayo", "Ngozi",
                   "Femi", "Halima", "Uche", "Yemi", "Aisha", "Obinna", "Funke", "Ibrahim", "Chioma", "Seyi",
                   "Musa", "Kemi", "Tobi", "Nneka", "Dayo", "Fatima", "Ikenna", "Bisi", "Sani", "Ebuka",
                   "Temi", "Hauwa", "Jide", "Ozioma", "Lola", "Nonso", "Rukayat", "Segun", "Adaeze", "Kelechi"]
    LAST_NAMES = ["Okafor", "Adeyemi", "Bello", "Eze", "Abubakar", "Okonkwo", "Balogun", "Nwosu", "Ibrahim",
                  "Ogunleye", "Musa", "Chukwu", "Adebayo", "Danjuma", "Obi", "Lawal", "Nnamdi", "Afolabi",
                  "Yusuf", "Onyeka", "Salami", "Umeh", "Garba", "Olatunji", "Ekwueme", "Aliyu"]

    PERSONAS = [
        Persona("commuter", 0.18, 6.0, 4, {FlightClass.ECONOMY: .55, FlightClass.BUSINESS: .42, FlightClass.FIRST: .03}, .35, (28, 52), .08),
        Persona("planner", 0.30, 1.4, 30, {FlightClass.ECONOMY: .93, FlightClass.BUSINESS: .06, FlightClass.FIRST: .01}, .45, (22, 60), .35),
        Persona("occasional", 0.46, 1.0, 9, {FlightClass.ECONOMY: .9, FlightClass.BUSINESS: .08, FlightClass.FIRST: .02}, .25, (18, 70), .28),
        Persona("premium", 0.06, 2.5, 6, {FlightClass.ECONOMY: .05, FlightClass.BUSINESS: .45, FlightClass.FIRST: .5}, .7, (35, 65), .15),
    ]

    # (origin, destination, departures/day weight, base fare, block minutes)
    ROUTES = [
        ("Lagos", "Abuja", 3.0, 85000, 75), ("Abuja", "Lagos", 3.0, 85000, 75),
        ("Lagos", "Port Harcourt", 2.0, 75000, 70), ("Port Harcourt", "Lagos", 2.0, 75000, 70),
        ("Lagos", "Kano", 1.2, 95000, 95), ("Kano", "Lagos", 1.2, 95000, 95),
        ("Abuja", "Port Harcourt", 1.0, 70000, 65), ("Lagos", "Enugu", 1.0, 72000, 65),
        ("Enugu", "Lagos", 1.0, 72000, 65), ("Abuja", "Kano", 0.6, 60000, 55),
        ("Lagos", "Calabar", 0.6, 78000, 80), ("Lagos", "Accra", 0.8, 145000, 70),
        ("Accra", "Lagos", 0.8, 145000, 70), ("Abuja", "Maiduguri", 0.4, 82000, 85),
        ("Lagos", "Owerri", 0.6, 70000, 65), ("Lagos", "Uyo", 0.5, 76000, 75),
    ]
    AIRCRAFT = [("Embraer E175", 78), ("Bombardier CRJ900", 90), ("Airbus A320", 150), ("Boeing 737-800", 162)]
    DEPARTURE_HOURS = [6, 7, 8, 10, 12, 14, 16, 18, 19]

    def __init__(self, system, seed=2026, days_back=60, days_forward=28, flights_per_day=2, passengers=3500):
        self.system = system
        self.rng = random.Random(seed)
        self.days_back = days_back
        self.days_forward = days_forward
        self.flights_per_day = flights_per_day
        self.passenger_count = passengers
        self._flight_seq = {}
        self._passport_seq = 1000

    # ------------------------------------------------------------------ public
    def run(self, moment=None):
        moment = (moment or clock_now()).replace(second=0, microsecond=0)
        real_notifications = self.system.notifications
        self.system.notifications = NotificationService(_NullNotifier())
        try:
            with self.system.storage.batch():
                passengers = self._make_passengers()
                flights = self._make_flights(moment) + self._make_demo_flights(moment)
                self._make_bookings(flights, passengers, moment)
                self._make_demo_traveller()
                self.system.create_admin("admin@flyte.ng", "FlyteAdmin2026", "Ops Admin")
        finally:
            self.system.notifications = real_notifications
        return {"flights": len(flights), "passengers": len(passengers), "bookings": len(self.system.bookings)}

    # ------------------------------------------------------------- internals
    def _make_passengers(self):
        out = []
        weights = [p.weight for p in self.PERSONAS]
        for _ in range(self.passenger_count):
            persona = self.rng.choices(self.PERSONAS, weights)[0]
            first, last = self.rng.choice(self.FIRST_NAMES), self.rng.choice(self.LAST_NAMES)
            self._passport_seq += 1
            passport = f"N{self.rng.randint(10, 99)}{self._passport_seq:05d}"
            passenger = Passenger(
                passport, f"{first} {last}", self.rng.randint(*persona.ages),
                f"+234 80{self.rng.randint(10000000, 99999999)}",
                f"{first.lower()}.{last.lower()}{self._passport_seq % 997}@example.com",
            )
            self.system.register_passenger(passenger)
            out.append((passenger, persona))
        return out

    def _flight_number(self, airline):
        self._flight_seq[airline.code] = self._flight_seq.get(airline.code, 100) + 1
        return f"{airline.code}{self._flight_seq[airline.code]}"

    def _make_flights(self, moment):
        """Each day, a few routes get flights from 2–3 competing airlines,
        each priced at that airline's fare level."""
        flights = []
        route_weights = [r[2] for r in self.ROUTES]
        airlines = AIRLINES.all()
        start = moment.replace(hour=0, minute=0) - timedelta(days=self.days_back)
        for day in range(self.days_back + self.days_forward + 1):
            date = start + timedelta(days=day)
            n = self.flights_per_day + (1 if date.weekday() in (0, 4) else 0)
            for origin, dest, _, fare, minutes in self.rng.choices(self.ROUTES, route_weights, k=n):
                for airline in self.rng.sample(airlines, self.rng.choice([2, 2, 3])):
                    hour = self.rng.choice(self.DEPARTURE_HOURS)
                    dep = date.replace(hour=hour, minute=self.rng.choice([0, 15, 30, 45]))
                    aircraft, capacity = self.rng.choices(self.AIRCRAFT, [4, 4, 2, 1])[0]
                    price = fare * airline.fare_level * self.rng.uniform(0.96, 1.04) // 500 * 500
                    flight = Flight(self._flight_number(airline), origin, dest, format_datetime(dep),
                                    format_datetime(dep + timedelta(minutes=minutes)), price, capacity, aircraft,
                                    airline=airline.name)
                    flight.created_at = format_datetime(dep - timedelta(days=90))
                    if dep < moment and self.rng.random() < airline.delay_rate:   # historic delays → OTP metric
                        flight.delay_minutes = self.rng.choice([10, 20, 25, 40, 60, 90, 120])
                    self.system.add_flight(flight)
                    flights.append(flight)
        return flights

    def _sample_lead(self, persona):
        return max(0.05, self.rng.expovariate(1 / persona.lead_mean))

    def _purchase_time(self, departure, lead_days):
        moment = departure - timedelta(days=lead_days)
        # People book in the morning and late evening; Sunday/Monday are busiest.
        hour = self.rng.choices(range(24), [1, 1, 1, 1, 1, 2, 3, 5, 8, 10, 10, 9, 8, 7, 7, 7, 6, 6, 7, 9, 10, 9, 5, 2])[0]
        moment = moment.replace(hour=hour, minute=self.rng.randint(0, 59))
        if moment.weekday() in (2, 3, 5) and self.rng.random() < 0.25:
            moment -= timedelta(days=1)
        return min(moment, departure - timedelta(hours=3))

    def _make_bookings(self, flights, passengers, moment):
        weighted = [p for p in passengers for _ in range(max(1, round(p[1].trips)))]
        for flight in flights:
            dep = flight.departure_dt
            # Popular routes, Fridays and morning flights sell better.
            # Cheaper airlines sell a little better.
            target = (self.rng.uniform(0.55, 0.92) + (0.05 if dep.weekday() == 4 else 0) + (0.04 if dep.hour < 9 else 0)
                      + 0.5 * (1 - flight.carrier.fare_level))
            seats_to_sell = int(min(0.98, target) * flight.capacity)
            requests = []
            for _ in range(seats_to_sell):
                passenger, persona = self.rng.choice(weighted)
                created = self._purchase_time(dep, self._sample_lead(persona))
                if created <= moment:                       # future flights fill only up to "now"
                    requests.append((created, passenger, persona))
            for created, passenger, persona in sorted(requests, key=lambda r: r[0]):
                cabin = self.rng.choices(list(persona.cabin_weights), list(persona.cabin_weights.values()))[0]
                seats = flight.available_seats(cabin) or flight.available_seats(FlightClass.ECONOMY)
                if not seats:
                    break
                seat = self.rng.choice(seats[: max(6, len(seats) // 2)])
                cabin = flight.cabin_for_seat(seat)
                if self.rng.random() < persona.insure:
                    tier = InsuranceTier.PREMIUM_COMPREHENSIVE if self.rng.random() < 0.3 else InsuranceTier.BASIC_MEDICAL
                else:
                    tier = InsuranceTier.EXISTING if self.rng.random() < 0.3 else InsuranceTier.NONE
                # No free checked bag (e.g. Lagoon Economy) → people buy one more often.
                bag_chance = persona.extra_bag * (2.0 if flight.carrier.baggage.included_bags(cabin) == 0 else 1.0)
                extra_bags = (2 if self.rng.random() < 0.2 else 1) if self.rng.random() < bag_chance else 0
                booking = self.system.create_booking(
                    passenger.passport, flight.number, cabin, seat, tier,
                    payment_ref=f"PAY_DEMO{self.rng.randint(10**7, 10**8)}", card_last4="4242",
                    moment=created, enforce_schedule=False, extra_bags=extra_bags,
                )
                # ~7% cancel later on.
                if self.rng.random() < 0.07:
                    cancel_at = created + (dep - created) * self.rng.uniform(0.1, 0.9)
                    if cancel_at <= moment:
                        self.system._cancel(booking, cancel_at)

    def _make_demo_flights(self, moment):
        """Two flights for the demo traveller – one inside the check-in window."""
        soon = (moment + timedelta(hours=20)).replace(minute=30)
        later = (moment + timedelta(days=12)).replace(hour=9, minute=40)
        flights = [
            Flight("LG420", "Lagos", "Abuja", format_datetime(soon), format_datetime(soon + timedelta(minutes=75)),
                   73000, 150, "Airbus A320", airline="Lagoon Airways"),
            Flight("ZJ777", "Lagos", "Accra", format_datetime(later), format_datetime(later + timedelta(minutes=70)),
                   166500, 162, "Boeing 737-800", airline="Zuma Jet"),
            Flight("ZJ778", "Accra", "Lagos", format_datetime(later + timedelta(days=5, hours=7)),
                   format_datetime(later + timedelta(days=5, hours=8, minutes=10)),
                   166500, 162, "Boeing 737-800", airline="Zuma Jet"),
        ]
        for flight in flights:
            self.system.add_flight(flight)
        return flights

    def _make_demo_traveller(self):
        """A ready-made account with a trip you can check in for right now."""
        system = self.system
        user = system.register_user("ada@flyte.ng", "Demo1234", name="Ada Okafor", passport="A12345678",
                                    age=24, phone="+234 803 555 0101")
        def window_seat(number, cabin):
            seats = system.get_flight(number).available_seats(cabin)
            return next((s for s in seats if s.endswith(("A", "F"))), seats[0])

        # A one-way flight tomorrow (check-in open now)…
        system.create_booking(user.passport, "LG420", FlightClass.ECONOMY, window_seat("LG420", FlightClass.ECONOMY),
                              InsuranceTier.BASIC_MEDICAL, payment_ref="PAY_DEMOLG420", card_last4="4242",
                              enforce_schedule=False, extra_bags=1)
        # …and a return trip to Accra, booked and paid as one Itinerary.
        system.book_trip(user.passport, TripType.RETURN, ["ZJ777", "ZJ778"],
                         [window_seat("ZJ777", FlightClass.BUSINESS), window_seat("ZJ778", FlightClass.BUSINESS)],
                         FlightClass.BUSINESS, InsuranceTier.PREMIUM_COMPREHENSIVE,
                         CardDetails("4242424242424242", "12/39", "123"))
