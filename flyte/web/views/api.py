"""JSON API used by the front-end (and handy for mobile clients later)."""

from flask import Blueprint, request

from airline.enums import FlightClass, InsuranceTier
from airline.models import AIRLINES, AIRPORTS

from ..security import Auth
from .base import JsonView

bp = Blueprint("api", __name__, url_prefix="/api")


class HealthApi(JsonView):
    def get(self):
        return self.ok(status="ok", flights=len(self.system.flights), storage=self.system.storage.describe())


class AirportsApi(JsonView):
    def get(self):
        return self.ok(airports=[a.to_dict() for a in AIRPORTS.all()])


class FlightSearchApi(JsonView):
    def get(self):
        flights = self.system.search_flights(origin=request.args.get("from") or None,
                                             destination=request.args.get("to") or None,
                                             departure_date=request.args.get("date") or None, bookable_only=True)
        return self.ok(flights=[f.summary() for f in flights[:100]])


class SeatMapApi(JsonView):
    def get(self, number):
        flight = self.system.get_flight(number)
        return self.ok(number=flight.number, columns=flight.SEAT_COLUMNS, rows=flight.seat_map(),
                       first_rows=flight.first_rows, business_rows=flight.business_rows)


class QuoteApi(JsonView):
    def get(self, number):
        cabin = FlightClass.parse(request.args.get("cabin", "Economy"))
        tier = InsuranceTier.parse(request.args.get("insurance", "None"))
        bags = int(request.args.get("bags", "0") or 0)
        quote = self.system.quote(number, cabin, tier, extra_bags=bags)
        return self.ok(quote.to_dict())


class AdviceApi(JsonView):
    def get(self, number):
        cabin = FlightClass.parse(request.args.get("cabin", "Economy"))
        return self.ok(self.system.fare_advice(number, cabin))


class AirlinesApi(JsonView):
    def get(self):
        return self.ok(airlines=[a.to_dict() for a in AIRLINES.all()])


class OverviewApi(JsonView):
    decorators = [Auth.admin_required]

    def get(self):
        return self.ok(self.analytics.overview())


bp.add_url_rule("/health", view_func=HealthApi.as_view("health"))
bp.add_url_rule("/airports", view_func=AirportsApi.as_view("airports"))
bp.add_url_rule("/airlines", view_func=AirlinesApi.as_view("airlines"))
bp.add_url_rule("/flights", view_func=FlightSearchApi.as_view("flights"))
bp.add_url_rule("/flights/<number>/seats", view_func=SeatMapApi.as_view("seats"))
bp.add_url_rule("/flights/<number>/quote", view_func=QuoteApi.as_view("quote"))
bp.add_url_rule("/flights/<number>/advice", view_func=AdviceApi.as_view("advice"))
bp.add_url_rule("/admin/overview", view_func=OverviewApi.as_view("overview"))
