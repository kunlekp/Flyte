"""Analytics + Flask integration tests."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airline.analytics import AnalyticsEngine, KMeans, SeasonalTrendForecaster
from airline.seed import DemoDataSeeder
from airline.services import AirlineSystem, SqliteStorage
from web import create_app
from web.config import TestConfig


class ForecastTests(unittest.TestCase):
    def test_recovers_trend_and_weekly_pattern(self):
        t = np.arange(70)
        weekly = np.array([0, 10, 0, -10, 15, -20, 5])[t % 7]
        y = 100 + 0.5 * t + weekly + np.random.default_rng(1).normal(0, 2, 70)
        model = SeasonalTrendForecaster(ridge=0.01).fit(y, start_dow=0)
        mean, low, high = model.predict(7)
        self.assertAlmostEqual(model.trend_per_day, 0.5, delta=0.1)
        self.assertTrue(np.all(low <= mean) and np.all(mean <= high))
        self.assertLess(model.backtest(y, 0, 14)["mape"], 0.05)


class KMeansTests(unittest.TestCase):
    def test_separates_blobs(self):
        rng = np.random.default_rng(0)
        X = np.vstack([rng.normal(c, 0.2, (50, 2)) for c in ((0, 0), (5, 5), (0, 5))])
        model = KMeans(k=3).fit(X)
        self.assertEqual(len(set(model.labels_)), 3)
        self.assertGreater(model.silhouette(X), 0.7)


class SeededTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = AirlineSystem(storage=SqliteStorage(":memory:"))
        DemoDataSeeder(cls.system, days_back=40, days_forward=14, passengers=600).run()
        cls.engine = AnalyticsEngine(cls.system)

    def test_overview_shape(self):
        o = self.engine.overview()
        self.assertIn("revenue", o["kpis"])
        self.assertTrue(0 < o["kpis"]["load_factor"]["value"] <= 1)
        self.assertEqual(len(o["forecast"]["forecast"]["mean"]), 14)
        self.assertEqual(len(o["segments"]["segments"]), 4)
        self.assertEqual(len(o["heatmap"]["grid"]), 7)

    def test_lead_time_fares_fall_with_advance_booking(self):
        rows = self.engine.lead_time_profile()
        self.assertGreater(rows[0]["avg_economy_fare"], rows[-1]["avg_economy_fare"])


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestConfig)
        cls.system = cls.app.extensions["airline"]
        cls.system.register_user("t@x.com", "pass1234", name="Test User", passport="T1234567", age=30, phone="+234 1")
        cls.system.create_admin("ops@x.com", "admin1234")

    def client_as(self, email, password):
        c = self.app.test_client()
        c.post("/login", data={"email": email, "password": password})
        return c

    def test_public_pages(self):
        c = self.app.test_client()
        for url in ("/", "/flights", "/login", "/signup", "/manage", "/api/health"):
            self.assertEqual(c.get(url).status_code, 200, url)
        number = next(iter(self.system.flights))
        self.assertEqual(c.get(f"/flights/{number}").status_code, 200)

    def test_checkout_flow(self):
        c = self.client_as("t@x.com", "pass1234")
        flight = self.system.upcoming_flights()[0]
        seat = flight.available_seats("Economy")[0]
        res = c.post(f"/book/{flight.number}", json={"cabin": "Economy", "seat": seat, "insurance": "None",
                                                     "card": {"number": "4242424242424242", "expiry": "12/30", "cvc": "123"}})
        self.assertEqual(res.status_code, 200, res.get_json())
        booking_id = res.get_json()["booking_id"]
        self.assertEqual(c.get(f"/trips/{booking_id}").status_code, 200)
        self.assertEqual(c.get("/trips").status_code, 200)

    def test_admin_requires_role(self):
        c = self.client_as("t@x.com", "pass1234")
        self.assertEqual(c.get("/admin/").status_code, 403)
        admin = self.client_as("ops@x.com", "admin1234")
        for url in ("/admin/", "/admin/flights", "/admin/bookings", "/admin/passengers", "/api/admin/overview",
                    "/admin/export/bookings.csv"):
            self.assertEqual(admin.get(url).status_code, 200, url)


if __name__ == "__main__":
    unittest.main()


class ProductionGuardTests(unittest.TestCase):
    def test_refuses_to_start_without_secret_key(self):
        from web.config import ProductionConfig

        class Prod(ProductionConfig):
            DATABASE_URL = "sqlite:///:memory:"
            SEED_DEMO = False
            ADMIN_EMAIL = ADMIN_PASSWORD = ""

        old = os.environ.pop("SECRET_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                create_app(Prod)
        finally:
            if old is not None:
                os.environ["SECRET_KEY"] = old
