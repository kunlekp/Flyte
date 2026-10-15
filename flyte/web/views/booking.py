"""Checkout endpoint (called by the booking stepper with fetch)."""

from flask import Blueprint, request, url_for

from airline.services import CardDetails

from ..security import Auth
from .base import JsonView

bp = Blueprint("booking", __name__)


class CheckoutView(JsonView):
    decorators = [Auth.login_required]

    def post(self, number):
        if not self.passenger:
            return self.fail("Admin accounts can't book trips. Log in with a traveller account.", 403)
        data = request.get_json(silent=True) or {}
        card_data = data.get("card") or {}
        card = CardDetails(card_data.get("number"), card_data.get("expiry"), card_data.get("cvc"),
                           card_data.get("holder", ""))
        booking = self.system.book_and_pay(
            self.passenger.passport, number, data.get("cabin", "Economy"), data.get("seat", ""),
            data.get("insurance", "None"), card, extra_bags=int(data.get("extra_bags", 0) or 0),
        )
        return self.ok(booking_id=booking.booking_id,
                       redirect=url_for("account.trip", booking_id=booking.booking_id, new=1))


bp.add_url_rule("/book/<number>", view_func=CheckoutView.as_view("checkout"), methods=["POST"])
