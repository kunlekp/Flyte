"""Passenger – the traveller profile (unchanged core from the console app)."""

from ..enums import LoyaltyTier


class Passenger:
    def __init__(
        self,
        passport,
        name,
        age,
        phone,
        email,
        miles=0,
        history=None
    ):
        self.passport = str(passport).upper()
        self.name = name
        self.age = int(age)
        self.phone = phone
        self.email = email
        self.miles = int(miles)
        self.history = list(history or [])

    # ---- booking history ----------------------------------------------------
    def add_booking(self, booking_id):
        if booking_id not in self.history:
            self.history.append(booking_id)

    def remove_booking(self, booking_id):
        if booking_id in self.history:
            self.history.remove(booking_id)

    # ---- loyalty ------------------------------------------------------------
    def earn_miles(self, miles):
        self.miles += int(miles)

    def revoke_miles(self, miles):
        self.miles = max(0, self.miles - int(miles))

    @property
    def loyalty_tier(self):
        return LoyaltyTier.for_miles(self.miles)

    @property
    def tier_progress(self):
        """0–1 progress toward the next tier (1.0 at the top tier)."""
        tier = self.loyalty_tier
        nxt = tier.next_tier()
        if nxt is None:
            return 1.0
        span = nxt.threshold - tier.threshold
        return (self.miles - tier.threshold) / span

    @property
    def miles_to_next_tier(self):
        nxt = self.loyalty_tier.next_tier()
        return 0 if nxt is None else nxt.threshold - self.miles

    @property
    def first_name(self):
        return (self.name or "").split(" ")[0]

    @property
    def initials(self):
        parts = [p for p in (self.name or "?").split() if p]
        return "".join(p[0] for p in parts[:2]).upper()

    # ---- serialisation ------------------------------------------------------
    def to_dict(self):
        return {
            "passport": self.passport,
            "name": self.name,
            "age": self.age,
            "phone": self.phone,
            "email": self.email,
            "miles": self.miles,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            passport=data.get("passport", data.get("passport_number", "")),
            name=data.get("name", ""),
            age=int(data.get("age", 0)),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            miles=int(data.get("miles", 0)),
            history=data.get("history", data.get("booking_history", [])),
        )

    def __repr__(self):
        return f"Passenger({self.passport}, {self.name!r})"
