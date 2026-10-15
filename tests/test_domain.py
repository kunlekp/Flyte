"""Unit tests for the OOP core.  Run:  python -m unittest discover -s tests -v"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airline import (AirlineSystem, Booking, CabinMismatchError, DuplicateError, FlightClass, InsuranceTier,
                     InvalidDataError, Passenger, SeatOccupiedError)
from airline.errors import CheckInError, PaymentError
from airline.models import Flight
from airline.services import CardDetails, JsonStorage, SqliteStorage
from airline.services.notifier import NotificationService, Notifier
from airline.utils import format_datetime

NOW = datetime(2026, 10, 15, 9, 0)


class Silent(Notifier):
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append((to, subject))


def make_system(storage=None):
    system = AirlineSystem(storage=storage or SqliteStorage(":memory:"), notifications=NotificationService(Silent()))
    dep = NOW + timedelta(days=5)
    system.add_flight(Flight("FY100", "Lagos", "Abuja", format_datetime(dep),
                             format_datetime(dep + timedelta(minutes=75)), 85000, 120))
    system.register_passenger(Passenger("A1234567", "Ada Okafor", 24, "+2348030000000", "ada@example.com"))
    return system


GOOD_CARD = CardDetails("4242 4242 4242 4242", "12/30", "123")


class FlightTests(unittest.TestCase):
    def test_cabins_and_seats(self):
        f = Flight("FY1", "Lagos", "Kano", "2026-11-01 08:00", "2026-11-01 09:30", 90000, 120)
        self.assertEqual(len(f.seats), 120)
        self.assertEqual(f.cabin_for_seat("1A"), FlightClass.FIRST)
        self.assertEqual(f.cabin_for_seat("4A"), FlightClass.BUSINESS)
        self.assertEqual(f.cabin_for_seat("20F"), FlightClass.ECONOMY)
        self.assertGreater(f.distance_km, 800)

    def test_validation(self):
        bad = Flight("FY2", "Lagos", "Lagos", "2026-11-01 08:00", "2026-11-01 07:00", 100, 60)
        with self.assertRaises(InvalidDataError):
            bad.validate()

    def test_round_trip_dict(self):
        f = Flight("FY3", "Lagos", "Kano", "2026-11-01 08:00", "2026-11-01 09:30", 90000, 60)
        f.reserve("10A", "X")
        g = Flight.from_dict(f.to_dict())
        self.assertEqual(g.seats["10A"], "X")
        self.assertEqual(g.first_rows, f.first_rows)


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.system = make_system()

    def test_book_and_pay_happy_path(self):
        b = self.system.book_and_pay("A1234567", "FY100", "Economy", "15C", "Basic Medical", GOOD_CARD, moment=NOW)
        self.assertEqual(b.status, "Confirmed")
        self.assertEqual(b.insurance_cost, 4500)
        self.assertTrue(b.payment_ref.startswith("PAY_"))
        self.assertGreater(b.miles_earned, 250)
        self.assertEqual(self.system.flights["FY100"].seats["15C"], "A1234567")

    def test_cannot_double_book_seat(self):
        self.system.book_and_pay("A1234567", "FY100", "Economy", "15C", "None", GOOD_CARD, moment=NOW)
        with self.assertRaises(SeatOccupiedError):
            self.system.book_and_pay("A1234567", "FY100", "Economy", "15C", "None", GOOD_CARD, moment=NOW)

    def test_cabin_must_match(self):
        with self.assertRaises(CabinMismatchError):
            self.system.create_booking("A1234567", "FY100", "Economy", "1A", "None", moment=NOW)

    def test_declined_card_books_nothing(self):
        declined = CardDetails("4000000000000002", "12/30", "123")
        with self.assertRaises(PaymentError):
            self.system.book_and_pay("A1234567", "FY100", "Economy", "15C", "None", declined, moment=NOW)
        self.assertIsNone(self.system.flights["FY100"].seats["15C"])
        self.assertEqual(len(self.system.bookings), 0)

    def test_server_side_insurance_price(self):
        b = self.system.create_booking("A1234567", "FY100", "Economy", "15A", "Premium Comprehensive",
                                       insurance_cost=1, moment=NOW)
        self.assertEqual(b.insurance_cost, InsuranceTier.PREMIUM_COMPREHENSIVE.price)

    def test_cancel_refund_and_miles(self):
        b = self.system.create_booking("A1234567", "FY100", "Economy", "15A", "None", moment=NOW)
        p = self.system.get_passenger("A1234567")
        self.assertGreater(p.miles, 0)
        self.system.cancel_booking(b.booking_id, moment=NOW)     # 5 days out → 90%
        self.assertAlmostEqual(b.refund_amount, round(b.ticket_price * 0.9, 2))
        self.assertEqual(p.miles, 0)
        self.assertIsNone(self.system.flights["FY100"].seats["15A"])
        self.assertIn(b.booking_id, p.history)                  # history kept

    def test_check_in_window(self):
        b = self.system.create_booking("A1234567", "FY100", "Economy", "15A", "None", moment=NOW)
        with self.assertRaises(CheckInError):
            self.system.check_in(b.booking_id, moment=NOW)
        later = self.system.flights["FY100"].departure_dt - timedelta(hours=3)
        self.system.check_in(b.booking_id, moment=later)
        self.assertEqual(b.status, "Checked in")
        self.assertIn(b.boarding_group, (3, 4, 5))

    def test_airline_cancellation_full_refund(self):
        b = self.system.create_booking("A1234567", "FY100", "Business", "4A", "None", moment=NOW)
        self.system.cancel_flight("FY100", moment=NOW)
        self.assertEqual(b.refund_amount, b.total_cost)

    def test_dynamic_price_rises_with_demand(self):
        empty = self.system.quote("FY100", "Economy", moment=NOW).fare
        flight = self.system.flights["FY100"]
        for seat in flight.available_seats("Economy")[:80]:
            flight.seats[seat] = "X"
        busy = self.system.quote("FY100", "Economy", moment=NOW).fare
        self.assertGreater(busy, empty)


class PersistenceTests(unittest.TestCase):
    def test_sqlite_and_json_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            for storage in (SqliteStorage(os.path.join(tmp, "a.db")), JsonStorage(os.path.join(tmp, "a.json"))):
                system = make_system(storage)
                system.create_booking("A1234567", "FY100", "Economy", "15A", "None", moment=NOW)
                fresh = AirlineSystem(storage=type(storage)(storage.path))
                fresh.load()
                self.assertEqual(len(fresh.bookings), 1)
                self.assertEqual(fresh.flights["FY100"].seats["15A"], "A1234567")

    def test_legacy_console_database_loads(self):
        legacy = {
            "booking_number": 1001,
            "flights": [{"flight_number": "NG101", "origin": "Lagos", "destination": "Abuja",
                         "departure": "2026-10-01 08:00", "arrival": "2026-10-01 09:15", "base_price": 85000,
                         "capacity": 120}],
            "passengers": [{"passport": "P1", "name": "Old Timer", "age": 40, "phone": "1", "email": "o@x.com"}],
            "bookings": [{"booking_id": "BK1001", "passport": "P1", "flight": "NG101", "flight_class": "Economy",
                          "seat": "10A"}],
        }
        system = AirlineSystem(storage=SqliteStorage(":memory:"))
        system.load_snapshot(legacy)
        self.assertEqual(system.bookings["BK1001"].ticket_price, 85000)
        self.assertEqual(system.flights["NG101"].seats["10A"], "P1")


class AccountTests(unittest.TestCase):
    def test_register_and_authenticate(self):
        system = make_system()
        system.register_user("new@x.com", "secret123", name="New Person", passport="B7654321", age=30, phone="+234 1")
        self.assertTrue(system.authenticate("NEW@x.com", "secret123"))
        with self.assertRaises(DuplicateError):
            system.register_user("new@x.com", "secret123", name="Dup", passport="C1111111", age=30, phone="1")

    def test_weak_password_rejected(self):
        system = make_system()
        with self.assertRaises(InvalidDataError):
            system.register_user("a@x.com", "short", name="A B", passport="D1111111", age=30, phone="1")


class CardTests(unittest.TestCase):
    def test_luhn_and_expiry(self):
        CardDetails("4242424242424242", "12/30", "123").validate()
        with self.assertRaises(PaymentError):
            CardDetails("4242424242424241", "12/30", "123").validate()
        with self.assertRaises(PaymentError):
            CardDetails("4242424242424242", "01/20", "123").validate()


if __name__ == "__main__":
    unittest.main()


class AirlineAndLuggageTests(unittest.TestCase):
    def setUp(self):
        self.system = make_system()
        dep = NOW + timedelta(days=5)
        for number, airline, price in (("LG100", "Lagoon Airways", 70000), ("ZJ100", "Zuma Jet", 95000)):
            self.system.add_flight(Flight(number, "Lagos", "Abuja", format_datetime(dep),
                                          format_datetime(dep + timedelta(minutes=75)), price, 120, airline=airline))

    def test_baggage_policy_fees(self):
        from airline.models import AIRLINES
        lagoon = AIRLINES.find("LG").baggage
        self.assertEqual(lagoon.included_bags("Economy"), 0)
        self.assertEqual(lagoon.fee_for(0), 0)
        self.assertEqual(lagoon.fee_for(2), 7500 + 12000)
        with self.assertRaises(InvalidDataError):
            lagoon.fee_for(4)

    def test_booking_with_extra_bags(self):
        b = self.system.book_and_pay("A1234567", "LG100", "Economy", "15A", "None", GOOD_CARD, moment=NOW, extra_bags=2)
        self.assertEqual(b.baggage_fee, 19500)
        self.assertEqual(b.total_cost, b.ticket_price + 19500)
        self.assertEqual(b.total_bags, 2)
        self.system.cancel_booking(b.booking_id, moment=NOW)          # >72h → 90% of fare + bags
        self.assertAlmostEqual(b.refund_amount, round((b.ticket_price + 19500) * 0.9, 2))

    def test_unknown_airline_still_works(self):
        self.assertEqual(self.system.flights["FY100"].carrier.code, "XX")

    def test_recommender_balances_price_and_seats(self):
        from airline.models import AIRLINES
        from airline.services import AirlineRecommender, FareOption
        cheap_but_full = FareOption(None, AIRLINES.find("LG"), 70000, 1, {"included_bags": 0})
        bit_dearer = FareOption(None, AIRLINES.find("HM"), 73000, 40, {"included_bags": 1})
        pricey = FareOption(None, AIRLINES.find("ZJ"), 110000, 60, {"included_bags": 2})
        pick = AirlineRecommender().recommend([cheap_but_full, bit_dearer, pricey])
        self.assertIs(pick.option, bit_dearer)
        self.assertIn("1 seat left", pick.reason)
        rows = AirlineRecommender().airline_summaries([cheap_but_full, bit_dearer, pricey])
        self.assertEqual([r["airline"].code for r in rows], ["LG", "HM", "ZJ"])


class TripTests(unittest.TestCase):
    def setUp(self):
        self.system = make_system()
        out = NOW + timedelta(days=5)
        back = NOW + timedelta(days=9)
        self.system.add_flight(Flight("FY200", "Abuja", "Lagos", format_datetime(back),
                                      format_datetime(back + timedelta(minutes=75)), 85000, 120))
        self.system.add_flight(Flight("FY300", "Abuja", "Kano", format_datetime(out + timedelta(hours=3)),
                                      format_datetime(out + timedelta(hours=4)), 60000, 120))

    def test_return_trip_is_discounted_and_paid_once(self):
        one_way = self.system.quote("FY100", "Economy", moment=NOW).fare
        quote = self.system.quote_trip("return", ["FY100", "FY200"], "Economy", moment=NOW)
        self.assertLess(quote["legs"][0]["fare"], one_way)
        self.assertGreater(quote["discount"], 0)
        trip = self.system.book_trip("A1234567", "return", ["FY100", "FY200"], ["15A", "15B"], "Economy",
                                     "Basic Medical", GOOD_CARD, moment=NOW)
        self.assertEqual(trip.leg_count, 2)
        self.assertEqual(trip.insurance_cost, 4500)          # cover charged once for the trip
        self.assertEqual(trip.route_label, "Lagos → Abuja → Lagos")
        self.assertAlmostEqual(trip.total_cost, quote["total"] + 4500, delta=1)

    def test_return_must_come_back(self):
        with self.assertRaises(InvalidDataError):
            self.system.book_trip("A1234567", "return", ["FY100", "FY300"], ["15A", "15B"], "Economy",
                                  "None", GOOD_CARD, moment=NOW)

    def test_multi_city_needs_time_to_connect(self):
        trip = self.system.book_trip("A1234567", "multi", ["FY100", "FY300"], ["15A", "15B"], "Economy",
                                     "None", GOOD_CARD, moment=NOW)
        self.assertEqual(trip.cities, ["Lagos", "Abuja", "Kano"])
        late = NOW + timedelta(days=5, minutes=80)      # FY100 lands at +75 min → 5 min to connect
        self.system.add_flight(Flight("FY301", "Abuja", "Kano", format_datetime(late),
                                      format_datetime(late + timedelta(hours=1)), 60000, 120))
        with self.assertRaises(InvalidDataError):
            self.system.book_trip("A1234567", "multi", ["FY100", "FY301"], ["16A", "16B"], "Economy",
                                  "None", GOOD_CARD, moment=NOW)

    def test_failed_payment_books_nothing(self):
        declined = CardDetails("4000000000000002", "12/30", "123")
        with self.assertRaises(PaymentError):
            self.system.book_trip("A1234567", "return", ["FY100", "FY200"], ["15A", "15B"], "Economy",
                                  "None", declined, moment=NOW)
        self.assertIsNone(self.system.flights["FY100"].seats["15A"])
        self.assertEqual(len(self.system.bookings), 0)
