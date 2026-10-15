"""Public pages: home, search results, flight detail, manage booking."""

from datetime import timedelta

from flask import Blueprint, redirect, render_template, request, url_for

from airline.enums import FlightClass, InsuranceTier, TripType
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
        try:
            trip = TripType.parse(request.args.get("trip") or "oneway")
        except ValueError:
            trip = TripType.ONE_WAY
        if trip != TripType.ONE_WAY:
            return TripSearch(self.system, self.now()).render(trip, request.args)
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
                                  "airline": airline_code, "trip": "oneway"},
                               airports=AIRPORTS.all(), cabins=list(FlightClass), today=moment.strftime("%Y-%m-%d"))


class TripSearch:
    """Return and multi-city search: one list of options per leg, each with
    its own recommended flight."""

    def __init__(self, system, moment):
        self.system = system
        self.moment = moment

    def render(self, trip, args):
        try:
            cabin = FlightClass.parse(args.get("cabin") or "Economy")
        except ValueError:
            cabin = FlightClass.ECONOMY
        planner = self.system.planner
        legs = planner.legs_for(trip, args.get("from", "").strip(), args.get("to", "").strip(),
                                args.get("date", "").strip(), args.get("return", "").strip(),
                                zip(args.getlist("leg_from"), args.getlist("leg_to"), args.getlist("leg_date")))
        q = {"trip": trip.slug, "from": args.get("from", ""), "to": args.get("to", ""), "date": args.get("date", ""),
             "return": args.get("return", ""), "cabin": cabin.value,
             "legs": [{"origin": l.origin, "destination": l.destination, "date": l.date} for l in legs]}
        error, sections = None, []
        try:
            results = planner.search(self.system, trip, legs, self.moment)
        except AirlineError as exc:
            error, results = exc.message, []
        builder = FlightCardBuilder(self.system, self.moment)
        recommender = AirlineRecommender()
        for result in results:
            cards = sorted((builder.build(f, cabin) for f in result.flights if f.available_count(cabin)),
                           key=lambda c: c["flight"].departure)
            pick = recommender.recommend([builder.as_option(c) for c in cards])
            for c in cards:
                c["is_pick"] = bool(pick) and c["flight"] is pick.option.flight
            sections.append({"result": result, "cards": cards, "pick": pick,
                             "pick_card": pick.option.extras["card"] if pick else None})
        return render_template("trip_results.html", trip=trip, sections=sections, error=error, q=q,
                               airports=AIRPORTS.all(), today=self.moment.strftime("%Y-%m-%d"))


class TripCheckoutView(BaseView):
    """Checkout for a return or multi-city trip: one cabin, a seat per flight,
    extra bags on every flight, cover once, one payment."""

    def get(self):
        moment = self.now()
        trip = TripType.parse(request.args.get("trip") or "return")
        numbers = [n.strip().upper() for n in request.args.getlist("f") if n.strip()]
        try:
            flights = [self.system.get_flight(n) for n in numbers]
            self.system.planner.validate(trip, flights)
            for f in flights:
                if not f.is_bookable(moment):
                    raise AirlineError(f"{f.number} is no longer open for booking. Pick another flight.")
        except AirlineError as error:
            return render_template("errors/error.html", code=400, message=error.message), 400
        cabins = []
        for cabin in FlightClass:
            seats = [f.available_count(cabin) for f in flights]
            if not all(f.cabin_capacity(cabin) for f in flights):
                continue
            fares = [self.system.pricing.quote(f, cabin, moment).fare for f in flights]
            cabins.append({"name": cabin.value, "fare": sum(fares), "seats_left": min(seats),
                           "perks": CABIN_PERKS[cabin]})
        legs = [{"flight": f, "carrier": f.carrier, "baggage": f.carrier.baggage.to_dict(),
                 "included": {c.value: f.carrier.baggage.included_bags(c) for c in FlightClass}} for f in flights]
        insurance = [{"name": t.value, "price": t.price, "blurb": t.blurb} for t in InsuranceTier]
        try:
            preferred = FlightClass.parse(request.args.get("cabin") or "Economy").value
        except ValueError:
            preferred = "Economy"
        return render_template("trip_checkout.html", trip=trip, legs=legs, cabins=cabins, insurance=insurance,
                               preferred=preferred, numbers=numbers)


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
bp.add_url_rule("/trip", view_func=TripCheckoutView.as_view("trip_checkout"))
