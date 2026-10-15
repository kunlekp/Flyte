"""Payment gateways.

``MockPaymentGateway`` lets the app run end-to-end with test cards. To go
live, implement ``PaymentGateway`` for Paystack/Flutterwave (charge + refund)
and select it in ``web/__init__.py`` – nothing else needs to change.
"""

import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..errors import PaymentError


@dataclass
class PaymentResult:
    success: bool
    reference: str
    amount: float
    last4: str
    message: str = ""


class CardDetails:
    def __init__(self, number, expiry, cvc, holder=""):
        self.number = "".join(ch for ch in str(number or "") if ch.isdigit())
        self.expiry = str(expiry or "").strip()
        self.cvc = str(cvc or "").strip()
        self.holder = holder.strip()

    @staticmethod
    def luhn_ok(number):
        digits = [int(d) for d in number][::-1]
        total = 0
        for index, digit in enumerate(digits):
            if index % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return total % 10 == 0

    @property
    def last4(self):
        return self.number[-4:]

    @property
    def brand(self):
        if self.number.startswith("4"):
            return "Visa"
        if self.number[:2] in {"51", "52", "53", "54", "55"} or self.number[:2] == "22":
            return "Mastercard"
        if self.number.startswith(("5060", "5061", "5078", "6500")):
            return "Verve"
        return "Card"

    def validate(self, today=None):
        if not 12 <= len(self.number) <= 19 or not self.luhn_ok(self.number):
            raise PaymentError("That card number doesn't look right. Check the digits.")
        try:
            month, year = self.expiry.replace(" ", "").split("/")
            month, year = int(month), int(year)
            year += 2000 if year < 100 else 0
        except ValueError:
            raise PaymentError("Enter the expiry as MM/YY.") from None
        today = today or datetime.now()
        if not 1 <= month <= 12 or (year, month) < (today.year, today.month):
            raise PaymentError("This card has expired.")
        if not self.cvc.isdigit() or len(self.cvc) not in (3, 4):
            raise PaymentError("Enter the 3-digit security code on the back of the card.")


class PaymentGateway(ABC):
    name = "abstract"

    @abstractmethod
    def charge(self, amount, card, description=""):
        """Return PaymentResult or raise PaymentError."""

    @abstractmethod
    def refund(self, reference, amount):
        """Return PaymentResult."""


class MockPaymentGateway(PaymentGateway):
    """Test-mode gateway. 4242 4242 4242 4242 succeeds;
    4000 0000 0000 0002 is declined; 4000 0000 0000 9995 has insufficient funds."""

    name = "mock"
    DECLINED = "4000000000000002"
    INSUFFICIENT = "4000000000009995"

    def __init__(self):
        self.ledger = []

    def charge(self, amount, card, description=""):
        card.validate()
        if card.number == self.DECLINED:
            raise PaymentError("Your card was declined. Try another card.")
        if card.number == self.INSUFFICIENT:
            raise PaymentError("Insufficient funds on this card.")
        result = PaymentResult(True, "PAY_" + secrets.token_hex(6).upper(), float(amount), card.last4, "Approved")
        self.ledger.append(("charge", result.reference, amount, description))
        return result

    def refund(self, reference, amount):
        result = PaymentResult(True, "RFD_" + secrets.token_hex(6).upper(), float(amount), "", "Refunded")
        self.ledger.append(("refund", reference, amount, ""))
        return result
