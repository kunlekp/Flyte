"""AnalyticsEngine – turns the live object graph into pandas DataFrames and
airline KPIs: revenue, load factor, RASK, OTP, lead time, forecasts and
customer segments. Everything returns plain JSON-ready dicts."""

from datetime import timedelta

import numpy as np
import pandas as pd

from ..enums import FlightClass, InsuranceTier
from ..utils import now as clock_now
from .forecasting import SeasonalTrendForecaster
from .segmentation import PassengerSegmenter


class AnalyticsEngine:
    LEAD_BINS = [0, 1, 3, 7, 14, 30, 10_000]
    LEAD_LABELS = ["< 1 day", "1–3 days", "3–7 days", "1–2 weeks", "2–4 weeks", "30+ days"]
    AGE_BINS = [0, 17, 24, 34, 44, 54, 64, 200]
    AGE_LABELS = ["Under 18", "18–24", "25–34", "35–44", "45–54", "55–64", "65+"]
    ON_TIME_MINUTES = 15

    def __init__(self, system):
        self.system = system
        self._cache_key = None
        self._cache = None

    # ------------------------------------------------------------------ frames
    def _signature(self):
        s = self.system
        return (len(s.bookings), len(s.flights), len(s.passengers),
                sum(1 for b in s.bookings.values() if not b.is_active), s.booking_number,
                sum(f.delay_minutes for f in s.flights.values()))

    def frames(self):
        key = self._signature()
        if key == self._cache_key:
            return self._cache
        bookings = pd.DataFrame([{
            "id": b.booking_id,
            "passport": b.passenger.passport,
            "flight": b.flight.number,
            "route": b.flight.route,
            "airline": b.flight.carrier.name,
            "extra_bags": b.extra_bags,
            "baggage_fee": b.baggage_fee,
            "cabin": b.flight_class,
            "insurance": b.insurance,
            "ticket": b.ticket_price,
            "insurance_cost": b.insurance_cost,
            "total": b.total_cost,
            "net": b.net_revenue,
            "refund": b.refund_amount,
            "active": b.is_active,
            "created_at": b.created_at,
            "departure": b.flight.departure,
            "age": b.passenger.age,
            "distance_km": b.flight.distance_km,
        } for b in self.system.bookings.values()])
        if not bookings.empty:
            bookings["created_at"] = pd.to_datetime(bookings["created_at"])
            bookings["departure"] = pd.to_datetime(bookings["departure"])
            bookings["lead_days"] = (bookings["departure"] - bookings["created_at"]).dt.total_seconds() / 86400
            bookings["created_date"] = bookings["created_at"].dt.normalize()

        flights = pd.DataFrame([{
            "number": f.number,
            "route": f.route,
            "airline": f.carrier.name,
            "origin": f.origin,
            "destination": f.destination,
            "departure": f.departure,
            "capacity": len(f.seats),
            "sold": f.occupied_count(),
            "distance_km": f.distance_km,
            "delay": f.delay_minutes,
            "cancelled": f.manual_status == "Cancelled",
            "aircraft": f.aircraft_type,
        } for f in self.system.flights.values()])
        if not flights.empty:
            flights["departure"] = pd.to_datetime(flights["departure"])
            flights["load_factor"] = flights["sold"] / flights["capacity"].clip(lower=1)
            flights["ask"] = flights["capacity"] * flights["distance_km"]   # available seat-km
        self._cache_key, self._cache = key, (bookings, flights)
        return self._cache

    @staticmethod
    def _delta(current, previous):
        if previous in (0, None) or current is None or pd.isna(previous):
            return None
        return round((current - previous) / abs(previous), 4)

    # -------------------------------------------------------------------- KPIs
    def kpis(self, moment=None, window_days=30):
        moment = pd.Timestamp(moment or clock_now())
        bookings, flights = self.frames()
        if bookings.empty or flights.empty:
            return {"empty": True}

        def window(offset):
            end = moment - pd.Timedelta(days=offset * window_days)
            start = end - pd.Timedelta(days=window_days)
            b = bookings[(bookings["created_at"] > start) & (bookings["created_at"] <= end)]
            f = flights[(flights["departure"] > start) & (flights["departure"] <= end) & ~flights["cancelled"]]
            fb = bookings[bookings["flight"].isin(f["number"]) & bookings["active"]]
            revenue = float(b["net"].sum())
            sold = int(f["sold"].sum())
            capacity = int(f["capacity"].sum())
            ask = float(f["ask"].sum())
            return {
                "revenue": revenue,
                "bookings": int(len(b)),
                "avg_fare": float(b.loc[b["active"], "ticket"].mean()) if len(b) else 0.0,
                "load_factor": sold / capacity if capacity else 0.0,
                "rask": float(fb["total"].sum()) / ask if ask else 0.0,      # ₦ per available seat-km
                "otp": float((f["delay"] < self.ON_TIME_MINUTES).mean()) if len(f) else None,
                "cancel_rate": float((~b["active"]).mean()) if len(b) else 0.0,
                "attach_rate": float(b["insurance"].isin([InsuranceTier.BASIC_MEDICAL.value,
                                                          InsuranceTier.PREMIUM_COMPREHENSIVE.value]).mean()) if len(b) else 0.0,
                "ancillary": float(b.loc[b["active"], ["insurance_cost", "baggage_fee"]].sum().sum()),
                "bag_rate": float((b["extra_bags"] > 0).mean()) if len(b) else 0.0,
                "lead_days": float(b["lead_days"].median()) if len(b) else 0.0,
                "flights_flown": int(len(f)),
            }

        current, previous = window(0), window(1)
        out = {key: {"value": value, "delta": self._delta(value, previous.get(key))} for key, value in current.items()}
        out["passengers"] = {"value": len(self.system.passengers), "delta": None}
        out["window_days"] = window_days
        return out

    # ------------------------------------------------------------ time series
    def daily_series(self, moment=None, days=60):
        moment = pd.Timestamp(moment or clock_now()).normalize()
        bookings, _ = self.frames()
        index = pd.date_range(moment - pd.Timedelta(days=days - 1), moment, freq="D")
        if bookings.empty:
            return {"dates": [d.strftime("%Y-%m-%d") for d in index], "bookings": [0] * days, "revenue": [0] * days}
        grouped = bookings.groupby("created_date").agg(bookings=("id", "count"), revenue=("net", "sum"))
        grouped = grouped.reindex(index, fill_value=0)
        ma = grouped["revenue"].rolling(7, min_periods=1).mean()
        return {
            "dates": [d.strftime("%Y-%m-%d") for d in index],
            "bookings": grouped["bookings"].astype(int).tolist(),
            "revenue": grouped["revenue"].round(0).tolist(),
            "revenue_ma7": ma.round(0).tolist(),
        }

    def forecast(self, moment=None, history_days=56, horizon=14):
        moment = pd.Timestamp(moment or clock_now()).normalize()
        # Today is still in progress, so train on complete days only.
        series = self.daily_series(moment - pd.Timedelta(days=1), history_days)
        values = np.array(series["bookings"], dtype=float)
        start = pd.Timestamp(series["dates"][0])
        model = SeasonalTrendForecaster().fit(values, start.dayofweek)
        mean, low, high = model.predict(horizon)
        future = pd.date_range(moment, periods=horizon, freq="D")
        backtest = SeasonalTrendForecaster().backtest(values, start.dayofweek, holdout=14)
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return {
            "history": {"dates": series["dates"], "values": values.astype(int).tolist(),
                        "fitted": np.round(model.fitted(), 1).tolist()},
            "forecast": {"dates": [d.strftime("%Y-%m-%d") for d in future],
                         "mean": np.round(mean, 1).tolist(), "low": np.round(low, 1).tolist(),
                         "high": np.round(high, 1).tolist()},
            "next_7_days": int(round(mean[:7].sum())),
            "trend_per_day": round(model.trend_per_day, 3),
            "weekly_pattern": dict(zip(weekdays, np.round(model.weekly_pattern, 1).tolist())),
            "backtest": backtest,
            "model": "Linear trend + day-of-week seasonality (ridge least squares), 80% interval",
        }

    # --------------------------------------------------------------- mixes
    def route_performance(self, moment=None, top=None):
        bookings, flights = self.frames()
        if bookings.empty:
            return []
        active = bookings[bookings["active"]]
        by_route = active.groupby("route").agg(revenue=("total", "sum"), bookings=("id", "count"),
                                               avg_fare=("ticket", "mean"))
        lf = flights.groupby("route").agg(load_factor=("load_factor", "mean"), flights=("number", "count"),
                                          distance_km=("distance_km", "first"), sold=("sold", "sum"),
                                          ask=("ask", "sum"))
        table = by_route.join(lf, how="outer").fillna(0)
        table["yield_per_km"] = table["revenue"] / (table["sold"] * table["distance_km"]).replace(0, np.nan)
        table = table.sort_values("revenue", ascending=False)
        if top:
            table = table.head(top)
        return [{"route": route, "revenue": round(r.revenue), "bookings": int(r.bookings),
                 "avg_fare": round(r.avg_fare), "load_factor": round(float(r.load_factor), 4), "flights": int(r.flights),
                 "distance_km": round(r.distance_km), "yield_per_km": round(float(r.yield_per_km or 0), 1)}
                for route, r in table.iterrows()]

    def airline_performance(self, moment=None):
        """One row per airline: share of bookings, price level, load factor,
        punctuality and how often its passengers buy extra bags."""
        bookings, flights = self.frames()
        if bookings.empty:
            return []
        active = bookings[bookings["active"]]
        by_airline = active.groupby("airline").agg(bookings=("id", "count"), revenue=("total", "sum"),
                                                   avg_fare=("ticket", "mean"), bag_fees=("baggage_fee", "sum"),
                                                   bag_rate=("extra_bags", lambda x: (x > 0).mean()))
        departed = flights[~flights["cancelled"] & (flights["departure"] < pd.Timestamp(moment or clock_now()))]
        ops = departed.groupby("airline").agg(flights=("number", "count"), load_factor=("load_factor", "mean"),
                                              otp=("delay", lambda d: (d < self.ON_TIME_MINUTES).mean()))
        table = by_airline.join(ops, how="outer").fillna(0).sort_values("revenue", ascending=False)
        total = table["revenue"].sum() or 1
        from ..models import AIRLINES
        out = []
        for name, r in table.iterrows():
            carrier = AIRLINES.resolve(name)
            out.append({"airline": name, "code": carrier.code, "colour": carrier.colour,
                        "bookings": int(r.bookings), "revenue_share": round(float(r.revenue / total), 4),
                        "avg_fare": round(float(r.avg_fare)), "flights": int(r.flights),
                        "load_factor": round(float(r.load_factor), 4), "otp": round(float(r.otp), 4),
                        "bag_rate": round(float(r.bag_rate), 4), "bag_fees": round(float(r.bag_fees))})
        return out

    def cabin_mix(self):
        bookings, _ = self.frames()
        if bookings.empty:
            return []
        active = bookings[bookings["active"]]
        out = []
        for cabin in FlightClass:
            group = active[active["cabin"] == cabin.value]
            out.append({"cabin": cabin.value, "bookings": int(len(group)),
                        "revenue": round(float(group["total"].sum())),
                        "avg_fare": round(float(group["ticket"].mean())) if len(group) else 0})
        return out

    def insurance_mix(self):
        bookings, _ = self.frames()
        if bookings.empty:
            return []
        counts = bookings[bookings["active"]]["insurance"].value_counts()
        return [{"tier": tier.value, "bookings": int(counts.get(tier.value, 0))} for tier in InsuranceTier]

    def lead_time_profile(self):
        """Bookings and average fare by how far ahead people book."""
        bookings, _ = self.frames()
        if bookings.empty:
            return []
        active = bookings[bookings["active"]].copy()
        active["bin"] = pd.cut(active["lead_days"], self.LEAD_BINS, labels=self.LEAD_LABELS, right=False)
        econ = active[active["cabin"] == FlightClass.ECONOMY.value]
        counts = active.groupby("bin", observed=False)["id"].count()
        fares = econ.groupby("bin", observed=False)["ticket"].mean()
        return [{"bin": label, "bookings": int(counts.get(label, 0)),
                 "avg_economy_fare": round(float(fares.get(label, 0) or 0))} for label in self.LEAD_LABELS]

    def booking_heatmap(self):
        """7×24 grid of bookings by weekday and hour of purchase."""
        bookings, _ = self.frames()
        grid = np.zeros((7, 24), dtype=int)
        if not bookings.empty:
            counts = bookings.groupby([bookings["created_at"].dt.dayofweek, bookings["created_at"].dt.hour])["id"].count()
            for (dow, hour), value in counts.items():
                grid[dow, hour] = value
        return {"days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "grid": grid.tolist(),
                "max": int(grid.max())}

    def age_profile(self):
        bookings, _ = self.frames()
        if bookings.empty:
            return []
        unique = bookings.drop_duplicates("passport")
        bins = pd.cut(unique["age"], self.AGE_BINS, labels=self.AGE_LABELS)
        counts = bins.value_counts()
        return [{"band": label, "passengers": int(counts.get(label, 0))} for label in self.AGE_LABELS]

    # --------------------------------------------------------------- customers
    def passenger_features(self):
        bookings, _ = self.frames()
        if bookings.empty:
            return pd.DataFrame(columns=PassengerSegmenter.FEATURES)
        active = bookings[bookings["active"]].copy()
        active["premium"] = active["cabin"] != FlightClass.ECONOMY.value
        features = active.groupby("passport").agg(trips=("id", "count"), spend=("total", "sum"),
                                                  lead_days=("lead_days", "median"),
                                                  premium_share=("premium", "mean"), age=("age", "first"))
        return features

    def segments(self, k=4):
        result = PassengerSegmenter(k=k).segment(self.passenger_features())
        result.pop("labels", None)
        return result

    def top_customers(self, limit=8):
        features = self.passenger_features()
        if features.empty:
            return []
        top = features.sort_values("spend", ascending=False).head(limit)
        out = []
        for passport, row in top.iterrows():
            p = self.system.passengers.get(passport)
            out.append({"passport": passport, "name": p.name if p else passport, "trips": int(row.trips),
                        "spend": round(row.spend), "tier": p.loyalty_tier.label if p else "",
                        "miles": p.miles if p else 0})
        return out

    # ------------------------------------------------------------- operations
    def departures_board(self, moment=None, hours=72, limit=12):
        moment = moment or clock_now()
        until = moment + timedelta(hours=hours)
        upcoming = sorted((f for f in self.system.flights.values()
                           if moment - timedelta(hours=2) <= f.expected_departure_dt <= until),
                          key=lambda f: f.expected_departure_dt)[:limit]
        return [f.summary(moment) for f in upcoming]

    def at_risk_flights(self, moment=None, days=10, limit=8):
        """Flights departing soon whose load factor trails the typical booking curve.

        Expected LF at d days out is learned from history: the share of each
        departed flight's final bookings that had already been made d days out.
        """
        moment = moment or clock_now()
        bookings, flights = self.frames()
        if bookings.empty:
            return []
        now_ts = pd.Timestamp(moment)
        departed = flights[(flights["departure"] < now_ts) & ~flights["cancelled"]]
        past = bookings[bookings["flight"].isin(departed["number"]) & bookings["active"]]
        final_lf = float(departed["load_factor"].mean()) if len(departed) else 0.75
        curve = {}
        for d in range(0, days + 1):
            share = float((past["lead_days"] >= d).mean()) if len(past) else 0.5
            curve[d] = final_lf * share

        out = []
        for f in self.system.flights.values():
            hours = f.hours_until_departure(moment)
            if not 0 < hours <= days * 24 or f.manual_status == "Cancelled":
                continue
            d = int(hours // 24)
            expected = curve.get(d, final_lf)
            gap = f.load_factor - expected
            if gap < -0.08:
                out.append({**f.summary(moment), "expected_load_factor": round(expected, 3),
                            "gap": round(gap, 3), "days_out": d})
        return sorted(out, key=lambda r: r["gap"])[:limit]

    def overview(self, moment=None):
        """Everything the admin dashboard needs in one call (memoised per data
        version and minute, so dashboard refreshes are cheap)."""
        stamp = (self._signature(), (moment or clock_now()).strftime("%Y%m%d%H%M"))
        if getattr(self, "_overview_key", None) == stamp:
            return self._overview
        self._overview_key, self._overview = stamp, self._build_overview(moment)
        return self._overview

    def _build_overview(self, moment=None):
        return {
            "kpis": self.kpis(moment),
            "series": self.daily_series(moment, 60),
            "forecast": self.forecast(moment),
            "routes": self.route_performance(moment, top=8),
            "airlines": self.airline_performance(moment),
            "cabins": self.cabin_mix(),
            "insurance": self.insurance_mix(),
            "lead_time": self.lead_time_profile(),
            "heatmap": self.booking_heatmap(),
            "ages": self.age_profile(),
            "segments": self.segments(),
            "top_customers": self.top_customers(),
            "at_risk": self.at_risk_flights(moment),
            "board": self.departures_board(moment),
        }
