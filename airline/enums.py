"""Enumerations shared across the domain."""

from enum import Enum


class FlightClass(Enum):
    ECONOMY = "Economy"
    BUSINESS = "Business"
    FIRST = "First"

    @classmethod
    def parse(cls, value):
        """Accept an enum, its value ("Business") or its name ("BUSINESS")."""
        if isinstance(value, cls):
            return value
        text = str(value or "").strip()
        for member in cls:
            if text.lower() in (member.value.lower(), member.name.lower()):
                return member
        raise ValueError(f"Unknown travel class: {value!r}")


class InsuranceTier(Enum):
    NONE = "None"
    EXISTING = "Existing Insurance"
    BASIC_MEDICAL = "Basic Medical"
    PREMIUM_COMPREHENSIVE = "Premium Comprehensive"

    @property
    def price(self):
        """Server-side price list (the console app hard-coded these)."""
        return {
            InsuranceTier.NONE: 0,
            InsuranceTier.EXISTING: 0,
            InsuranceTier.BASIC_MEDICAL: 4500,
            InsuranceTier.PREMIUM_COMPREHENSIVE: 15000,
        }[self]

    @property
    def blurb(self):
        return {
            InsuranceTier.NONE: "Fly without cover.",
            InsuranceTier.EXISTING: "You already have a policy. We'll note it on your booking.",
            InsuranceTier.BASIC_MEDICAL: "Emergency medical up to ₦2M and lost-baggage support.",
            InsuranceTier.PREMIUM_COMPREHENSIVE: "Medical up to ₦10M, trip cancellation, delays and baggage.",
        }[self]

    @classmethod
    def parse(cls, value):
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().lower()
        for member in cls:
            if text in (member.value.lower(), member.name.lower()):
                return member
        raise ValueError(f"Unknown insurance option: {value!r}")


class BookingStatus(Enum):
    CONFIRMED = "Confirmed"
    CHECKED_IN = "Checked in"
    CANCELLED = "Cancelled"
    FLOWN = "Flown"


class FlightStatus(Enum):
    SCHEDULED = "Scheduled"
    DELAYED = "Delayed"
    BOARDING = "Boarding"
    IN_AIR = "In the air"
    LANDED = "Landed"
    CANCELLED = "Cancelled"


class TripType(Enum):
    ONE_WAY = "One-way"
    RETURN = "Return"
    MULTI_CITY = "Multi-city"

    @classmethod
    def parse(cls, value):
        """Accept the enum, its value, its name, or URL forms 'oneway' / 'return' / 'multi'."""
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")
        aliases = {"oneway": cls.ONE_WAY, "return": cls.RETURN, "multicity": cls.MULTI_CITY, "multi": cls.MULTI_CITY}
        if text in aliases:
            return aliases[text]
        raise ValueError(f"Unknown trip type: {value!r}")

    @property
    def fare_discount(self):
        """Booking out and back together is cheaper than two one-way tickets."""
        return {"One-way": 0.0, "Return": 0.08, "Multi-city": 0.0}[self.value]

    @property
    def slug(self):
        return {"One-way": "oneway", "Return": "return", "Multi-city": "multi"}[self.value]


class Role(Enum):
    PASSENGER = "passenger"
    ADMIN = "admin"


class LoyaltyTier(Enum):
    """(display name, miles needed). Ordered lowest → highest."""
    BLUE = ("Blue", 0)
    SILVER = ("Silver", 10_000)
    GOLD = ("Gold", 25_000)
    PLATINUM = ("Platinum", 50_000)

    @property
    def label(self):
        return self.value[0]

    @property
    def threshold(self):
        return self.value[1]

    @classmethod
    def for_miles(cls, miles):
        tier = cls.BLUE
        for member in cls:
            if miles >= member.threshold:
                tier = member
        return tier

    def next_tier(self):
        members = list(type(self))
        index = members.index(self)
        return members[index + 1] if index + 1 < len(members) else None
