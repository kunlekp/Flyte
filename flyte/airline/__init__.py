"""Flyte airline domain package – the OOP core used by both the web app and
the original console interface."""

from .enums import BookingStatus, FlightClass, FlightStatus, InsuranceTier, LoyaltyTier, Role
from .errors import *  # noqa: F401,F403
from .models import (AIRLINES, AIRPORTS, Airline, Airport, AirportDirectory, BaggagePolicy, Booking, Flight,
                     Passenger, User)
from .services import AirlineSystem

__version__ = "1.0.0"
