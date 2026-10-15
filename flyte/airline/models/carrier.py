"""Airlines (carriers) that sell seats on Flyte, and their baggage rules.

Flyte works like a travel platform: several airlines fly the same routes at
different prices with different baggage allowances. The carriers below are
FICTIONAL demo airlines with made-up prices.
"""

from ..enums import FlightClass
from ..errors import InvalidDataError


class BaggagePolicy:
    """How many checked bags each cabin includes, and what extra bags cost."""

    MAX_EXTRA_BAGS = 3

    def __init__(self, included, bag_kg, first_extra_fee, next_extra_fee, cabin_bag_kg=7):
        # included = {FlightClass.ECONOMY: 1, FlightClass.BUSINESS: 2, ...}
        self.included = {FlightClass.parse(k): int(v) for k, v in included.items()}
        self.bag_kg = int(bag_kg)
        self.first_extra_fee = float(first_extra_fee)
        self.next_extra_fee = float(next_extra_fee)
        self.cabin_bag_kg = int(cabin_bag_kg)

    def included_bags(self, flight_class):
        return self.included.get(FlightClass.parse(flight_class), 0)

    def fee_for(self, extra_bags):
        """Fee for checked bags ON TOP of the allowance."""
        extra = int(extra_bags or 0)
        if extra < 0 or extra > self.MAX_EXTRA_BAGS:
            raise InvalidDataError(f"You can add between 0 and {self.MAX_EXTRA_BAGS} extra bags.")
        if extra == 0:
            return 0.0
        return self.first_extra_fee + (extra - 1) * self.next_extra_fee

    def allowance_label(self, flight_class):
        bags = self.included_bags(flight_class)
        cabin = f"{self.cabin_bag_kg}kg cabin bag"
        if bags == 0:
            return f"{cabin} only"
        return f"{bags} × {self.bag_kg}kg checked bag{'s' if bags > 1 else ''} + {cabin}"

    def to_dict(self):
        return {
            "included": {k.value: v for k, v in self.included.items()},
            "bag_kg": self.bag_kg,
            "first_extra_fee": self.first_extra_fee,
            "next_extra_fee": self.next_extra_fee,
            "cabin_bag_kg": self.cabin_bag_kg,
            "max_extra": self.MAX_EXTRA_BAGS,
        }


class Airline:
    def __init__(self, code, name, fare_level, baggage, colour="#5b3df5", tagline="", delay_rate=0.15):
        self.code = code.upper()
        self.name = name
        self.fare_level = float(fare_level)   # price level vs the route average (1.0 = average)
        self.baggage = baggage                # composition: an Airline HAS a BaggagePolicy
        self.colour = colour
        self.tagline = tagline
        self.delay_rate = delay_rate          # used only to generate demo history

    def to_dict(self, flight_class=FlightClass.ECONOMY):
        return {"code": self.code, "name": self.name, "colour": self.colour, "tagline": self.tagline,
                "fare_level": self.fare_level, "baggage": self.baggage.to_dict(),
                "allowance": self.baggage.allowance_label(flight_class)}

    def __repr__(self):
        return f"Airline({self.code}, {self.name!r})"


class AirlineDirectory:
    """Registry of carriers. Unknown names (e.g. flights from the old console
    database) get a generic carrier so nothing breaks."""

    def __init__(self, airlines):
        self._by_code = {a.code: a for a in airlines}

    def find(self, text):
        if not text:
            return None
        key = str(text).strip()
        if key.upper() in self._by_code:
            return self._by_code[key.upper()]
        for airline in self._by_code.values():
            if airline.name.casefold() == key.casefold():
                return airline
        return None

    def resolve(self, text):
        """Always returns an Airline: the known one, or a generic stand-in."""
        found = self.find(text)
        if found:
            return found
        name = (text or "Independent carrier").strip() or "Independent carrier"
        return Airline("XX", name, 1.0, GENERIC_BAGGAGE, colour="#6f6b98")

    def all(self):
        return sorted(self._by_code.values(), key=lambda a: a.name)


E, B, F = FlightClass.ECONOMY, FlightClass.BUSINESS, FlightClass.FIRST
GENERIC_BAGGAGE = BaggagePolicy({E: 1, B: 2, F: 3}, 23, 10_000, 15_000)

AIRLINES = AirlineDirectory([
    Airline("HM", "Harmattan Air", 1.00, BaggagePolicy({E: 1, B: 2, F: 3}, 20, 9_000, 14_000),
            colour="#e0912b", tagline="Reliable all-rounder", delay_rate=0.15),
    Airline("LG", "Lagoon Airways", 0.86, BaggagePolicy({E: 0, B: 1, F: 2}, 20, 7_500, 12_000),
            colour="#0f9a9a", tagline="Low fares, pay for bags", delay_rate=0.18),
    Airline("SX", "Savannah Express", 0.95, BaggagePolicy({E: 1, B: 2, F: 2}, 23, 10_000, 15_000),
            colour="#4f8f2f", tagline="Big network up north", delay_rate=0.26),
    Airline("ZJ", "Zuma Jet", 1.15, BaggagePolicy({E: 2, B: 2, F: 3}, 23, 12_000, 16_000),
            colour="#d1435b", tagline="Premium, two bags free", delay_rate=0.08),
])
