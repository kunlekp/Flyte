"""Public pages: home, search results, flight detail, manage booking."""

from datetime import timedelta

from flask import Blueprint, redirect, render_template, request, url_for

from airline.enums import FlightClass, InsuranceTier
from airline.errors import AirlineError
from airline.models import AIRLINES, AIRPORTS
from airline.services import AirlineRecommender, FareOption

from .base import BaseView

bp = Blueprint("public", __name__)


class FlightCardBuilder:
    """Decorates flights with the live fare + trend shown on cards."""

    def __init__(self, system, moment):
        self.system = system
        self.moment = moment
        self.velocity = system.booking_velocities(moment=moment)

    def build(self, flight, cabin=FlightClass.ECONOMY):
        quote = self.system.pricing.quote(flight, cabin, self.moment)
        advice = self.system.advisor.advise(flight, cabin, self.velocity.get(flight.number, 0), self.moment)
        carrier = flight.carrier
        return {
            "flight": flight,
            "airline": carrier,
            "allowance": carrier.baggage.allowance_label(cabin),
            "included_bags": carrier.baggage.included_bags(cabin),
            "summary": flight.summary(self.moment),
            "fare": quote.fare,
            "cabin": FlightClass.parse(cabin).value,
            "cabin_seats_left": flight.available_count(cabin),
            "trend": advice["verdict"],
            "trend_change": advice["change_3d"],
        }

    @staticmethod
    def as_option(card):
        return FareOption(card["flight"], card["airline"], card["fare"], card["cabin_seats_left"],
                          {"included_bags": card["included_bags"], "card": card})


class HomeView(BaseView):
    def get(self):
        moment = self.now()
        builder = FlightCardBuilder(self.system, moment)
        seen, cards = set(), []
        for flight in self.system.upcoming_flights(moment):
            if flight.route in seen or flight.hours_until_departure(moment) < 6:
                continue
            seen.add(flight.route)
            cards.append(builder.build(flight))
            if len(cards) == 6:
                break
        routes = sorted({(f.origin_code, f.destination_code) for f in self.system.flights.values()})
        network = {
            "airports": [a.to_dict() for a in AIRPORTS.all()],
            "routes": [list(r) for r in routes],
        }
        return render_template("home.html", cards=cards, network=network, airports=AIRPORTS.all(),
                               today=moment.strftime("%Y-%m-%d"))


class FlightsView(BaseView):
    SORTS = {
        "departure": lambda c: c["flight"].departure,
        "price": lambda c: c["fare"],
        "duration": lambda c: c["flight"].duration_minutes,
    }

    def get(self):
        moment = self.now()
        origin = request.args.get("from", "").strip()
        destination = request.args.get("to", "").strip()
        date = request.args.get("date", "").strip()
        sort = request.args.get("sort", "departure")
        airline_code = request.args.get("airline", "").strip().upper()
        try:
            cabin = FlightClass.parse(request.args.get("cabin") or "Economy")
        except ValueError:
            cabin = FlightClass.ECONOMY

        flights = self.system.search_flights(origin=origin or None, destination=destination or None,
                                             departure_date=date or None, bookable_only=True, moment=moment)
        if not date:
            horizon = moment + timedelta(days=21)
            flights = [f for f in flights if f.departure_dt <= horizon]
        builder = FlightCardBuilder(self.system, moment)
        all_cards = [builder.build(f, cabin) for f in flights[:80] if f.available_count(cabin)]

        # Recommend across ALL airlines, then apply the airline filter.
        recommender = AirlineRecommender()
        options = [builder.as_option(c) for c in all_cards]
        pick = recommender.recommend(options)
        airlines = recommender.airline_summaries(options)
        for c in all_cards:
            c["is_pick"] = bool(pick) and c["flight"] is pick.option.flight
        cards = [c for c in all_cards if not airline_code or c["airline"].code == airline_code]
        cards.sort(key=self.SORTS.get(sort, self.SORTS["departure"]))

        nearby = []
        if not cards and date:            # suggest the same route on other days
            alt = self.system.search_flights(origin=origin or None, destination=destination or None,
                                             bookable_only=True, moment=moment)
            nearby = [builder.build(f, cabin) for f in alt[:4]]
        cheapest = min((c["fare"] for c in cards), default=None)
        return render_template("flights.html", cards=cards, nearby=nearby, cheapest=cheapest,
                               pick=pick, pick_card=pick.option.extras["card"] if pick else None, airlines=airlines,
                               q={"from": origin, "to": destination, "date": date, "cabin": cabin.value, "sort": sort,
                                  "airline": airline_code},
                               airports=AIRPORTS.all(), cabins=list(FlightClass), today=moment.strftime("%Y-%m-%d"))


class FlightDetailView(BaseView):
    def get(self, number):
        moment = self.now()
        flight = self.system.get_flight(number)
        carrier = flight.carrier
        cabins = []
        for cabin in FlightClass:
            capacity = flight.cabin_capacity(cabin)
            if not capacity:
                continue
            quote = self.system.pricing.quote(flight, cabin, moment)
            cabins.append({"name": cabin.value, "fare": quote.fare, "list_price": quote.list_price,
                           "seats_left": flight.available_count(cabin), "capacity": capacity,
                           "perks": [carrier.baggage.allowance_label(cabin)] + CABIN_PERKS[cabin],
                           "included_bags": carrier.baggage.included_bags(cabin)})
        insurance = [{"name": t.value, "price": t.price, "blurb": t.blurb} for t in InsuranceTier]
        return render_template("flight.html", flight=flight, summary=flight.summary(moment), cabins=cabins,
                               insurance=insurance, bookable=flight.is_bookable(moment), carrier=carrier,
                               baggage=carrier.baggage.to_dict())


CABIN_PERKS = {   # bag allowance comes from the airline's BaggagePolicy
    FlightClass.ECONOMY: ["Snack and drink", "Choose any economy seat"],
    FlightClass.BUSINESS: ["Lounge access", "Priority boarding"],
    FlightClass.FIRST: ["Chauffeur drop-off", "Board first, leave first"],
}


class ManageBookingView(BaseView):
    def get(self):
        return render_template("manage.html")

    def post(self):
        reference = request.form.get("reference", "").strip().upper()
        email = request.form.get("email", "").strip()
        try:
            booking = self.system.find_booking(reference, email)
        except AirlineError as error:
            return render_template("manage.html", error=error.message, reference=reference, email=email), 404
        if self.user and self.passenger and booking.passenger.passport == self.passenger.passport:
            return redirect(url_for("account.trip", booking_id=booking.booking_id))
        return render_template("manage.html", booking=booking, moment=self.now())


bp.add_url_rule("/", view_func=HomeView.as_view("home"))
bp.add_url_rule("/flights", view_func=FlightsView.as_view("flights"))
bp.add_url_rule("/flights/<number>", view_func=FlightDetailView.as_view("flight"))
bp.add_url_rule("/manage", view_func=ManageBookingView.as_view("manage"))
