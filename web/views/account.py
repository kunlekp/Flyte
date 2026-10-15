"""Traveller account: trips, boarding pass, check-in, cancel, profile."""

import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from airline.errors import AirlineError
from airline.enums import LoyaltyTier

from ..security import Auth
from .base import BaseView

bp = Blueprint("account", __name__)


class QRCodeRenderer:
    """Server-side QR via `segno` (in requirements.txt). If it's missing the
    boarding pass simply shows the reference in large type instead."""

    # Newer segno releases reject "currentColor", so draw in black and swap the
    # colour afterwards; the QR then follows the page's light/dark theme.
    _BLACK = re.compile(r'(stroke|fill)="#0{3}(?:0{3})?"')

    @classmethod
    def svg(cls, data):
        try:
            import segno
            markup = segno.make(data, error="m").svg_inline(scale=4, border=0, dark="#000", light=None)
        except Exception:          # missing library or any rendering problem: show the reference instead
            return None
        return cls._BLACK.sub(r'\1="currentColor"', markup)


class OwnedBookingMixin:
    def owned_booking(self, booking_id):
        booking = self.system.get_booking(booking_id)
        if self.user.is_admin:
            return booking
        if not self.passenger or booking.passenger.passport != self.passenger.passport:
            abort(404)
        return booking


class TripsView(BaseView):
    decorators = [Auth.login_required]

    def get(self):
        if not self.passenger:
            return redirect(url_for("admin.dashboard"))
        moment = self.now()
        bookings = self.system.bookings_for(self.passenger.passport)
        upcoming = sorted((b for b in bookings if b.flight.arrival_dt >= moment and b.is_active),
                          key=lambda b: b.flight.departure)
        past = [b for b in bookings if b not in upcoming]
        return render_template("account/trips.html", upcoming=upcoming, past=past, moment=moment)


class TripView(OwnedBookingMixin, BaseView):
    decorators = [Auth.login_required]

    def get(self, booking_id):
        booking = self.owned_booking(booking_id)
        moment = self.now()
        can_check_in, check_in_note = booking.check_in_window(moment)
        refund_amount, refund_note = self.system.refund_policy.refund_for(booking, moment)
        qr = QRCodeRenderer.svg(f"FLYTE|{booking.booking_id}|{booking.flight.number}|{booking.seat}|"
                                f"{booking.passenger.passport}") if booking.is_active else None
        itinerary = self.system.trip_for(booking)
        return render_template("account/trip.html", booking=booking, flight=booking.flight, moment=moment,
                               itinerary=itinerary,
                               can_check_in=can_check_in, check_in_note=check_in_note,
                               refund_amount=refund_amount, refund_note=refund_note, qr=qr,
                               is_new=request.args.get("new") == "1")


class ItineraryView(BaseView):
    """All flights of a return or multi-city trip on one page."""
    decorators = [Auth.login_required]

    def get(self, trip_id):
        trip = self.system.get_trip(trip_id)
        if not self.user.is_admin and (not self.passenger or trip.passenger.passport != self.passenger.passport):
            abort(404)
        return render_template("account/itinerary.html", trip=trip, moment=self.now(),
                               is_new=request.args.get("new") == "1")


class CheckInView(OwnedBookingMixin, BaseView):
    decorators = [Auth.login_required]

    def post(self, booking_id):
        booking = self.owned_booking(booking_id)
        try:
            self.system.check_in(booking.booking_id)
            flash(f"You're checked in. Boarding group {booking.boarding_group}.", "success")
        except AirlineError as error:
            flash(error.message, "error")
        return redirect(url_for("account.trip", booking_id=booking.booking_id))


class CancelView(OwnedBookingMixin, BaseView):
    decorators = [Auth.login_required]

    def post(self, booking_id):
        booking = self.owned_booking(booking_id)
        try:
            note = self.system.cancel_booking(booking.booking_id)
            flash(f"Booking cancelled. {note}", "success")
        except AirlineError as error:
            flash(error.message, "error")
        return redirect(url_for("account.trip", booking_id=booking.booking_id))


class ProfileView(BaseView):
    decorators = [Auth.login_required]

    def get(self):
        if not self.passenger:
            return redirect(url_for("admin.dashboard"))
        bookings = [b for b in self.system.bookings_for(self.passenger.passport) if b.is_active]
        stats = {
            "trips": len(bookings),
            "km": round(sum(b.flight.distance_km for b in bookings)),
            "cities": len({b.flight.destination for b in bookings}),
            "spent": sum(b.total_cost for b in bookings),
        }
        return render_template("account/profile.html", p=self.passenger, stats=stats, tiers=list(LoyaltyTier))

    def post(self):
        try:
            self.system.update_passenger(self.passenger.passport, name=request.form.get("name"),
                                         phone=request.form.get("phone"))
            flash("Profile saved.", "success")
        except AirlineError as error:
            flash(error.message, "error")
        return redirect(url_for("account.profile"))


bp.add_url_rule("/trips", view_func=TripsView.as_view("trips"))
bp.add_url_rule("/trips/trip/<trip_id>", view_func=ItineraryView.as_view("itinerary"))
bp.add_url_rule("/trips/<booking_id>", view_func=TripView.as_view("trip"))
bp.add_url_rule("/trips/<booking_id>/check-in", view_func=CheckInView.as_view("check_in"), methods=["POST"])
bp.add_url_rule("/trips/<booking_id>/cancel", view_func=CancelView.as_view("cancel"), methods=["POST"])
bp.add_url_rule("/profile", view_func=ProfileView.as_view("profile"))
