"""AirlineRecommender – picks the best-value flight in a search and summarises
what each airline offers on that search."""

from dataclasses import dataclass, field

from ..utils import money


@dataclass
class FareOption:
    """One bookable flight in a search result, as the recommender sees it."""
    flight: object
    airline: object
    fare: float
    seats_left: int
    extras: dict = field(default_factory=dict)   # anything the caller wants to carry along

    @property
    def included_bags(self):
        return self.extras.get("included_bags", 0)


@dataclass
class Recommendation:
    option: FareOption
    score: float
    reason: str
    cheapest_fare: float


class AirlineRecommender:
    """Score = 70% price + 30% availability.

    price        = cheapest fare in the search ÷ this fare      (1.0 for the cheapest)
    availability = seats left in the cabin ÷ 12, capped at 1.0   (a near-full flight is risky)
    """

    PRICE_WEIGHT = 0.70
    SEATS_WEIGHT = 0.30
    COMFORTABLE_SEATS = 12

    def score(self, option, cheapest):
        price = cheapest / option.fare if option.fare else 0.0
        seats = min(1.0, option.seats_left / self.COMFORTABLE_SEATS)
        return self.PRICE_WEIGHT * price + self.SEATS_WEIGHT * seats

    def recommend(self, options):
        options = [o for o in options if o.seats_left > 0]
        if not options:
            return None
        cheapest = min(o.fare for o in options)
        best = max(options, key=lambda o: (self.score(o, cheapest), -o.fare))
        return Recommendation(best, round(self.score(best, cheapest), 3), self._reason(best, options, cheapest), cheapest)

    def _reason(self, best, options, cheapest):
        name = best.airline.name
        if best.fare == cheapest:
            reason = f"Cheapest fare in this search, with {best.seats_left} seats left."
        else:
            low = min((o for o in options if o.fare == cheapest), key=lambda o: o.seats_left)
            reason = (f"Only {money(best.fare - cheapest).replace('.00', '')} more than the cheapest flight, "
                      f"which has just {low.seats_left} seat{'s' if low.seats_left != 1 else ''} left.")
        if best.included_bags == 0:
            reason += f" Checked bags cost extra on {name}."
        return reason

    def airline_summaries(self, options):
        """Cheapest fare, number of flights and seats left, per airline."""
        rows = {}
        for o in options:
            row = rows.setdefault(o.airline.code, {"airline": o.airline, "from_fare": o.fare, "flights": 0,
                                                   "seats_left": 0, "included_bags": o.included_bags})
            row["from_fare"] = min(row["from_fare"], o.fare)
            row["flights"] += 1
            row["seats_left"] += o.seats_left
        return sorted(rows.values(), key=lambda r: r["from_fare"])
