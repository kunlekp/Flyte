"""Notifications. ``LogNotifier`` writes emails to data/outbox.log for local
demos; ``SmtpNotifier`` sends real email once SMTP_* env vars are set."""

import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from ..utils import money, timestamp

log = logging.getLogger("flyte.notify")


class Notifier(ABC):
    @abstractmethod
    def send(self, to, subject, body):
        ...


class LogNotifier(Notifier):
    def __init__(self, path="data/outbox.log"):
        self.path = path

    def send(self, to, subject, body):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as file:
            file.write(f"--- {timestamp()} → {to}\nSubject: {subject}\n\n{body}\n\n")
        log.info("Email to %s: %s", to, subject)


class SmtpNotifier(Notifier):
    def __init__(self, host, port, username, password, sender):
        self.host, self.port = host, int(port)
        self.username, self.password, self.sender = username, password, sender

    def send(self, to, subject, body):
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self.sender, to, subject
        message.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(self.username, self.password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as error:   # never break a booking over email
            log.error("Email to %s failed: %s", to, error)


class NotificationService:
    """Turns domain events into human messages."""

    def __init__(self, notifier):
        self.notifier = notifier

    def booking_confirmed(self, booking):
        f = booking.flight
        self.notifier.send(
            booking.passenger.email,
            f"You're going to {f.destination} ✈ {booking.booking_id}",
            f"Hi {booking.passenger.first_name},\n\n"
            f"Booking {booking.booking_id} is confirmed.\n"
            f"{f.number}  {f.origin} → {f.destination}\n"
            f"{f.carrier.name} · Departs {f.departure} · Seat {booking.seat} · {booking.flight_class}\n"
            f"Checked bags: {booking.total_bags} ({booking.extra_bags} extra)\n"
            f"Paid {money(booking.total_cost)} (card ending {booking.card_last4})\n"
            f"Miles earned: {booking.miles_earned:,}\n\n"
            "Online check-in opens 24 hours before departure.\n— Flyte",
        )

    def booking_cancelled(self, booking, refund_note):
        self.notifier.send(
            booking.passenger.email,
            f"Booking {booking.booking_id} cancelled",
            f"Hi {booking.passenger.first_name},\n\nYour booking on {booking.flight.number} is cancelled.\n"
            f"Refund: {money(booking.refund_amount)} – {refund_note}\n— Flyte",
        )

    def checked_in(self, booking):
        self.notifier.send(
            booking.passenger.email,
            f"Boarding pass · {booking.flight.number} · Seat {booking.seat}",
            f"You're checked in. Boarding group {booking.boarding_group}. "
            f"Gate closes 20 minutes before departure ({booking.flight.departure}).\n— Flyte",
        )

    def flight_disrupted(self, booking, headline):
        self.notifier.send(booking.passenger.email, f"{booking.flight.number}: {headline}",
                           f"Hi {booking.passenger.first_name},\n\n{headline}\n— Flyte")
