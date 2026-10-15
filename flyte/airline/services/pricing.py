"""Revenue management: dynamic fares, fare forecasts, refunds and miles.

This is the "data science meets business rules" layer. Each concern is its
own small class so it can be swapped or unit-tested on its own.
"""

import math
from dataclasses import dataclass, asdict, field
from datetime import timedelta

from ..enums import FlightClass, InsuranceTier, LoyaltyTier
from ..utils import now as clock_now


@dataclass
class FareQuote:
    flight_number: str
    flight_class: str
    list_price: float          # base × cabin multiplier
    demand_multiplier: float   # from cabin load factor
    time_multiplier: float     # from days to departure
    fare: float                # what the customer pays (rounded)
    cabin_load_factor: float
    days_to_departure: float
    insurance: str = InsuranceTier.NONE.value
    insurance_cost: float = 0.0
    extra_bags: int = 0
    baggage_fee: float = 0.0
    included_bags: int = 0
    airline: str = ""

    @property
    def total(self):
        return self.fare + self.insurance_cost + self.baggage_fee

    def with_baggage(self, policy, extra_bags):
        self.extra_bags = int(extra_bags or 0)
        self.baggage_fee = float(policy.fee_for(self.extra_bags))
        self.included_bags = policy.included_bags(self.flight_class)
        return self

    def with_insurance(self, tier):
        tier = InsuranceTier.parse(tier)
        self.insurance = tier.value
        self.insurance_cost = float(tier.price)
        return self

    def to_dict(self):
        data = asdict(self)
        data["total"] = self.total
        return data


class PricingEngine:
    """Load-factor and time-to-departure based dynamic pricing.

    demand  = 0.90 + 0.75·LF²          (empty cabin 0.90× → full cabin 1.65×)
    time    = 0.95 + 0.45·e^(−days/5)  (far out 0.95× → day-of 1.40×)
    fare    = list_price × clamp(demand × time, floor, ceiling), rounded to ₦100
    """

    def __init__(self, floor=0.85, ceiling=2.0, rounding=100):
        self.floor = floor
        self.ceiling = ceiling
        self.rounding = rounding

    @staticmethod
    def demand_multiplier(load_factor):
        return 0.90 + 0.75 * max(0.0, min(1.0, load_factor)) ** 2

    @staticmethod
    def time_multiplier(days):
        return 0.95 + 0.45 * math.exp(-max(0.0, days) / 5)

    def _round(self, value):
        return round(value / self.rounding) * self.rounding

    def price_for(self, flight, flight_class, load_factor, days):
        cabin = FlightClass.parse(flight_class)
        list_price = flight.class_price(cabin)
        demand = self.demand_multiplier(load_factor)
        timing = self.time_multiplier(days)
        combined = max(self.floor, min(self.ceiling, demand * timing))
        return FareQuote(
            flight_number=flight.number,
            flight_class=cabin.value,
            list_price=list_price,
            demand_multiplier=round(demand, 4),
            time_multiplier=round(timing, 4),
            fare=float(self._round(list_price * combined)),
            cabin_load_factor=round(load_factor, 4),
            days_to_departure=round(days, 2),
            airline=flight.carrier.name,
            included_bags=flight.carrier.baggage.included_bags(cabin),
        )

    def quote(self, flight, flight_class, moment=None):
        moment = moment or clock_now()
        days = max(0.0, flight.hours_until_departure(moment) / 24)
        return self.price_for(flight, flight_class, flight.cabin_load_factor(flight_class), days)


class FareAdvisor:
    """Projects the fare curve forward using recent booking velocity and tells
    the traveller whether to book now or wait – a mini price-prediction model."""

    def __init__(self, pricing_engine):
        self.pricing = pricing_engine

    def project(self, flight, flight_class, daily_bookings, moment=None, horizon_days=14):
        moment = moment or clock_now()
        cabin = FlightClass.parse(flight_class)
        capacity = max(1, flight.cabin_capacity(cabin))
        cabin_share = capacity / max(1, len(flight.seats))
        lf_now = flight.cabin_load_factor(cabin)
        days_now = max(0.0, flight.hours_until_departure(moment) / 24)
        horizon = int(min(horizon_days, math.floor(days_now)))

        points = []
        for step in range(0, horizon + 1):
            # Bookings accelerate as departure nears (empirical ~1/sqrt(days)).
            days_left = days_now - step
            accel = 1 + 1.5 / math.sqrt(max(days_left, 1))
            extra = daily_bookings * cabin_share * accel * step
            lf = min(1.0, lf_now + extra / capacity)
            quote = self.pricing.price_for(flight, cabin, lf, days_left)
            points.append({
                "date": (moment + timedelta(days=step)).strftime("%Y-%m-%d"),
                "days_left": round(days_left, 1),
                "fare": quote.fare,
                "load_factor": round(lf, 3),
            })
        return points

    def advise(self, flight, flight_class, daily_bookings, moment=None):
        points = self.project(flight, flight_class, daily_bookings, moment)
        now_fare = points[0]["fare"]
        look_ahead = points[min(3, len(points) - 1)]["fare"]
        low = min(p["fare"] for p in points)
        change = (look_ahead - now_fare) / now_fare if now_fare else 0
        if change > 0.03:
            verdict, message = "rising", f"Book now — fares likely up {change:.0%} within 3 days."
        elif low < now_fare * 0.97:
            verdict, message = "falling", "Fares may dip a little. Set a reminder and check back."
        else:
            verdict, message = "steady", "Fares look steady for the next few days."
        return {"verdict": verdict, "message": message, "change_3d": round(change, 4), "curve": points}


class RefundPolicy:
    """Refund rules applied at cancellation time."""

    FULL_FEE_FREE_HOURS = 72
    HALF_REFUND_HOURS = 24
    LATE_FEE = 0.10

    def refund_for(self, booking, moment=None, airline_cancelled=False):
        if airline_cancelled:
            return booking.total_cost, "Full refund – the airline cancelled this flight."
        hours = booking.flight.hours_until_departure(moment)
        if hours <= 0:
            return 0.0, "No refund after departure."
        base = booking.refundable_base          # fare + extra-bag fees
        if booking.insurance == InsuranceTier.PREMIUM_COMPREHENSIVE.value:
            return base, "Premium cover: full fare and bag fees refunded (cover fee kept)."
        if hours >= self.FULL_FEE_FREE_HOURS:
            amount = base * (1 - self.LATE_FEE)
            return amount, "90% of the fare and bag fees refunded (10% change fee)."
        if hours >= self.HALF_REFUND_HOURS:
            return base * 0.5, "50% of the fare and bag fees refunded (within 72h of departure)."
        return 0.0, "No refund within 24h of departure."


class LoyaltyProgram:
    """Distance-based miles (replaces the console app's flat 500 miles)."""

    CLASS_BONUS = {FlightClass.ECONOMY: 1.0, FlightClass.BUSINESS: 1.5, FlightClass.FIRST: 2.0}
    TIER_BONUS = {LoyaltyTier.BLUE: 0.0, LoyaltyTier.SILVER: 0.10, LoyaltyTier.GOLD: 0.25, LoyaltyTier.PLATINUM: 0.50}
    MINIMUM = 250

    def miles_for(self, distance_km, flight_class, tier=LoyaltyTier.BLUE):
        base = distance_km * 0.621371 * self.CLASS_BONUS[FlightClass.parse(flight_class)]
        return int(max(self.MINIMUM, round(base * (1 + self.TIER_BONUS[tier]))))
