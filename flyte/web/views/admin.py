"""Operations console for staff: analytics, flights, bookings, passengers."""

import csv
import io

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from airline.errors import AirlineError
from airline.models import AIRLINES, AIRPORTS, Flight
from airline.utils import flight_number_valid, format_datetime, parse_datetime

from ..security import Auth
from .base import BaseView

bp = Blueprint("admin", __name__, url_prefix="/admin")


class AdminView(BaseView):
    decorators = [Auth.admin_required]
    PAGE_SIZE = 50

    @staticmethod
    def page():
        try:
            return max(1, int(request.args.get("page", 1)))
        except ValueError:
            return 1

    def paginate(self, items):
        page = self.page()
        start = (page - 1) * self.PAGE_SIZE
        return items[start:start + self.PAGE_SIZE], {
            "page": page, "pages": max(1, -(-len(items) // self.PAGE_SIZE)), "total": len(items)}


class DashboardView(AdminView):
    def get(self):
        return render_template("admin/dashboard.html")


class FlightsAdminView(AdminView):
    def get(self):
        moment = self.now()
        q = request.args.get("q", "").strip().lower()
        when = request.args.get("when", "upcoming")
        flights = sorted(self.system.flights.values(), key=lambda f: f.departure, reverse=(when == "past"))
        if when == "upcoming":
            flights = [f for f in flights if f.arrival_dt >= moment]
        elif when == "past":
            flights = [f for f in flights if f.arrival_dt < moment]
        if q:
            flights = [f for f in flights if q in f.number.lower() or q in f.origin.lower() or q in f.destination.lower()]
        rows, pager = self.paginate(flights)
        return render_template("admin/flights.html", flights=rows, pg=pager, q=q, when=when, moment=moment,
                               airports=AIRPORTS.all(), airlines=AIRLINES.all(), form={})

    def post(self):
        form = {k: request.form.get(k, "").strip() for k in
                ("number", "origin", "destination", "departure", "arrival", "price", "capacity", "aircraft_type", "airline")}
        try:
            number = form["number"].upper()
            if not flight_number_valid(number):
                raise AirlineError("Flight numbers look like FY123 – two letters then 2–4 digits.")
            flight = Flight(number, form["origin"], form["destination"],
                            format_datetime(parse_datetime(form["departure"])),
                            format_datetime(parse_datetime(form["arrival"])),
                            float(form["price"] or 0), int(form["capacity"] or 0), form["aircraft_type"] or "Airbus A320",
                            airline=(AIRLINES.find(form["airline"]) or AIRLINES.resolve(form["airline"])).name)
            self.system.add_flight(flight)
            flash(f"{flight.number} added to the schedule.", "success")
            return redirect(url_for("admin.flights"))
        except (AirlineError, ValueError) as error:
            flash(getattr(error, "message", str(error)), "error")
            return redirect(url_for("admin.flights", open="new"))


class FlightActionView(AdminView):
    def post(self, number, action):
        try:
            if action == "delay":
                minutes = int(request.form.get("minutes", "0") or 0)
                self.system.delay_flight(number, minutes)
                flash(f"{number.upper()} delay set to {minutes} min. Passengers notified.", "success")
            elif action == "cancel":
                refunded = self.system.cancel_flight(number)
                flash(f"{number.upper()} cancelled. {refunded} bookings refunded in full.", "success")
            elif action == "remove":
                self.system.remove_flight(number)
                flash(f"{number.upper()} removed.", "success")
            elif action == "fare":
                self.system.update_flight(number, price=request.form.get("price"))
                flash(f"{number.upper()} base fare updated.", "success")
            else:
                flash("Unknown action.", "error")
        except (AirlineError, ValueError) as error:
            flash(getattr(error, "message", str(error)), "error")
        return redirect(request.referrer or url_for("admin.flights"))


class BookingsAdminView(AdminView):
    def get(self):
        q = request.args.get("q", "").strip().lower()
        status = request.args.get("status", "")
        bookings = sorted(self.system.bookings.values(), key=lambda b: b.created_at, reverse=True)
        if status:
            bookings = [b for b in bookings if b.status == status]
        if q:
            bookings = [b for b in bookings if q in b.booking_id.lower() or q in b.passenger.name.lower()
                        or q in b.flight.number.lower() or q in b.passenger.passport.lower()]
        rows, pager = self.paginate(bookings)
        return render_template("admin/bookings.html", bookings=rows, pg=pager, q=q, status=status)


class PassengersAdminView(AdminView):
    def get(self):
        q = request.args.get("q", "").strip().lower()
        features = self.analytics.passenger_features()
        passengers = sorted(self.system.passengers.values(), key=lambda p: p.miles, reverse=True)
        if q:
            passengers = [p for p in passengers if q in p.name.lower() or q in p.passport.lower() or q in p.email.lower()]
        rows, pager = self.paginate(passengers)
        spend = features["spend"].to_dict() if not features.empty else {}
        trips = features["trips"].to_dict() if not features.empty else {}
        return render_template("admin/passengers.html", passengers=rows, pg=pager, q=q, spend=spend, trips=trips)


class ExportView(AdminView):
    """CSV exports for notebooks / BI tools."""

    def get(self, kind):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        if kind == "bookings":
            writer.writerow(["booking_id", "created_at", "airline", "flight", "route", "departure", "cabin", "seat",
                             "insurance", "extra_bags", "ticket_price", "insurance_cost", "baggage_fee", "total",
                             "status", "refund", "lead_days", "passenger_age", "loyalty_tier"])
            for b in self.system.bookings.values():
                writer.writerow([b.booking_id, b.created_at, b.flight.carrier.name, b.flight.number, b.flight.route,
                                 b.flight.departure, b.flight_class, b.seat, b.insurance, b.extra_bags, b.ticket_price,
                                 b.insurance_cost, b.baggage_fee, b.total_cost,
                                 b.status, b.refund_amount, round(b.lead_days, 2), b.passenger.age,
                                 b.passenger.loyalty_tier.label])
        elif kind == "flights":
            writer.writerow(["number", "airline", "route", "departure", "arrival", "aircraft", "capacity", "sold",
                             "load_factor", "base_fare", "distance_km", "delay_minutes", "status"])
            for f in self.system.flights.values():
                writer.writerow([f.number, f.carrier.name, f.route, f.departure, f.arrival, f.aircraft_type, len(f.seats),
                                 f.occupied_count(), round(f.load_factor, 4), f.price, round(f.distance_km),
                                 f.delay_minutes, f.status().value])
        elif kind == "passengers":
            # No names/emails/phones in exports – analysts get pseudonymous data only.
            writer.writerow(["passenger_key", "age", "miles", "tier", "bookings"])
            for index, p in enumerate(self.system.passengers.values()):
                writer.writerow([f"P{index:05d}", p.age, p.miles, p.loyalty_tier.label, len(p.history)])
        else:
            return Response("Unknown export", status=404)
        return Response(buffer.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=flyte_{kind}.csv"})


bp.add_url_rule("/", view_func=DashboardView.as_view("dashboard"))
bp.add_url_rule("/flights", view_func=FlightsAdminView.as_view("flights"))
bp.add_url_rule("/flights/<number>/<action>", view_func=FlightActionView.as_view("flight_action"), methods=["POST"])
bp.add_url_rule("/bookings", view_func=BookingsAdminView.as_view("bookings"))
bp.add_url_rule("/passengers", view_func=PassengersAdminView.as_view("passengers"))
bp.add_url_rule("/export/<kind>.csv", view_func=ExportView.as_view("export"))
