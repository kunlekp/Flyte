"""ItineraryPlanner – turns a trip request (one-way, return or multi-city)
into a search per leg, and checks a chosen set of flights makes a valid trip."""

from dataclasses import dataclass, field
from datetime import timedelta

from ..enums import TripType
from ..errors import InvalidDataError
from ..utils import now as clock_now, parse_datetime


@dataclass
class LegRequest:
    """What the traveller asked for on one leg of the trip."""
    origin: str
    destination: str
    date: str = ""            # 'YYYY-MM-DD', or '' for "any day"


@dataclass
class LegResult:
    """The search result for one leg."""
    index: int
    request: LegRequest
    flights: list = field(default_factory=list)
    exact_date: bool = True   # False → no flights that day, showing nearby dates


class ItineraryPlanner:
    MIN_CONNECTION = timedelta(minutes=60)   # time to change planes / reach the next airport
    MAX_LEGS = 4
    NEARBY_DAYS = 3

    # ---- building the request ----------------------------------------------
    def legs_for(self, trip_type, origin="", destination="", date="", return_date="", multi=()):
        """Expand a search form into LegRequests."""
        trip_type = TripType.parse(trip_type)
        if trip_type == TripType.ONE_WAY:
            return [LegRequest(origin, destination, date)]
        if trip_type == TripType.RETURN:
            return [LegRequest(origin, destination, date), LegRequest(destination, origin, return_date)]
        legs = [LegRequest(o.strip(), d.strip(), (dt or "").strip()) for o, d, dt in multi if o.strip() and d.strip()]
        return legs[: self.MAX_LEGS]

    def check_request(self, trip_type, legs):
        trip_type = TripType.parse(trip_type)
        if not legs or any(not leg.origin or not leg.destination for leg in legs):
            raise InvalidDataError("Enter where you're flying from and to.")
        if any(leg.origin.casefold() == leg.destination.casefold() for leg in legs):
            raise InvalidDataError("Each flight needs a different origin and destination.")
        if trip_type == TripType.MULTI_CITY and not 2 <= len(legs) <= self.MAX_LEGS:
            raise InvalidDataError(f"A multi-city trip has 2 to {self.MAX_LEGS} flights.")
        dates = [leg.date for leg in legs if leg.date]
        if dates != sorted(dates):
            raise InvalidDataError("Put the flights in date order: each one on or after the one before.")

    # ---- searching -------------------------------------------------------------
    def search(self, system, trip_type, legs, moment=None):
        """One LegResult per leg. Empty dates fall back to the next 2 weeks after
        the previous leg; empty days fall back to ±3 days."""
        moment = moment or clock_now()
        self.check_request(trip_type, legs)
        results, earliest = [], moment
        for index, leg in enumerate(legs):
            flights = system.search_flights(origin=leg.origin, destination=leg.destination,
                                            departure_date=leg.date or None, bookable_only=True, moment=moment)
            exact = True
            if not leg.date:
                flights = [f for f in flights if earliest <= f.departure_dt <= earliest + timedelta(days=14)]
            elif not flights:
                exact = False
                day = parse_datetime(leg.date)
                window = (day - timedelta(days=self.NEARBY_DAYS), day + timedelta(days=self.NEARBY_DAYS + 1))
                flights = [f for f in system.search_flights(origin=leg.origin, destination=leg.destination,
                                                            bookable_only=True, moment=moment)
                           if window[0] <= f.departure_dt < window[1]]
            results.append(LegResult(index, leg, flights[:40], exact))
            if leg.date:
                earliest = max(earliest, parse_datetime(leg.date))
        return results

    # ---- validating a choice ------------------------------------------------
    def validate(self, trip_type, flights):
        """`flights` = Flight objects in travel order. Raises InvalidDataError."""
        trip_type = TripType.parse(trip_type)
        expected = {TripType.ONE_WAY: (1, 1), TripType.RETURN: (2, 2), TripType.MULTI_CITY: (2, self.MAX_LEGS)}
        low, high = expected[trip_type]
        if not low <= len(flights) <= high:
            raise InvalidDataError(f"A {trip_type.value.lower()} trip needs {low if low == high else f'{low} to {high}'} "
                                   f"flight{'s' if high > 1 else ''}.")
        if len({f.number for f in flights}) != len(flights):
            raise InvalidDataError("The same flight is in your trip twice.")
        if trip_type == TripType.RETURN:
            out, back = flights
            if back.origin != out.destination or back.destination != out.origin:
                raise InvalidDataError("A return flight must go back the way you came.")
        for before, after in zip(flights, flights[1:]):
            gap = after.expected_departure_dt - (before.arrival_dt + timedelta(minutes=before.delay_minutes))
            if gap < self.MIN_CONNECTION:
                raise InvalidDataError(
                    f"{after.number} leaves before you can make it from {before.number}. "
                    f"Leave at least {int(self.MIN_CONNECTION.total_seconds() // 60)} minutes between flights.")
        return True
