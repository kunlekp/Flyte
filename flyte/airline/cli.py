"""Console interface – the ORIGINAL ConsoleUI from the coursework project,
kept working on top of the new AirlineSystem. Run:  python -m airline.cli
Both the terminal app and the web app share the same database."""

import os

from .enums import FlightClass, InsuranceTier
from .errors import AirlineError
from .models import Flight, Passenger
from .utils import email_valid, money


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nPress Enter to continue...")


def ask(prompt, required=True): # Ask for user input with optional required validation.
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("This field is required.")


def ask_int(prompt, minimum=None, maximum=None):
    while True:
        try:
            value = int(input(prompt).strip())
            if minimum is not None and value < minimum:
                print(f"Enter a value of at least {minimum}.")
                continue
            if maximum is not None and value > maximum:
                print(f"Enter a value not greater than {maximum}.")
                continue
            return value
        except ValueError:
            print("Enter a valid number.")


def ask_float(prompt, minimum=None):
    while True:
        try:
            value = float(input(prompt).strip())
            if minimum is not None and value < minimum:
                print(f"Enter a value of at least {minimum}.")
                continue
            return value
        except ValueError:
            print("Enter a valid amount.")


# =========================
# CONSOLE USER INTERFACE
# =========================

class ConsoleUI:
    def __init__(self, system):
        self.system = system

    # -------------------------
    # DISPLAY
    # -------------------------

    def header(self, title):
        clear()
        print("=" * 70)
        print(f"{title:^70}")
        print("=" * 70)

    def show_flight(self, flight):
        print(
            f"{flight.number:<10}"
            f"{flight.origin:<18}"
            f"{flight.destination:<18}"
            f"{flight.departure:<20}"
            f"{money(flight.price):>12}"
        )

    def list_flights(self):
        self.header("AVAILABLE FLIGHTS")

        if not self.system.flights:
            print("No flights available.")
            pause()
            return

        print(
            f"{'Flight':<10}"
            f"{'Origin':<18}"
            f"{'Destination':<18}"
            f"{'Departure':<20}"
            f"{'Price':>12}"
        )
        print("-" * 80)

        for flight in self.system.flights.values():
            self.show_flight(flight)

        pause()

    # -------------------------
    # REGISTER PASSENGER
    # -------------------------

    def register_passenger(self):
        self.header("REGISTER PASSENGER")

        passport = ask("Passport number: ").upper()

        if passport in self.system.passengers:
            print("A passenger with that passport already exists.")
            pause()
            return

        name = ask("Full name: ")
        age = ask_int("Age: ", 1, 120)
        phone = ask("Phone number: ")

        while True:
            email = ask("Email: ")
            if email_valid(email):
                break
            print("Enter a valid email address.")

        passenger = Passenger(
            passport,
            name,
            age,
            phone,
            email
        )

        try:
            self.system.register_passenger(passenger)
            print("\nPassenger registered successfully.")
        except AirlineError as error:
            print(f"\nError: {error}")

        pause()

    # -------------------------
    # SEARCH FLIGHTS
    # -------------------------

    def search_flights(self):
        self.header("SEARCH FLIGHTS")

        keyword = ask(
            "Search by flight number, origin or destination: "
        )

        results = self.system.search_flights(keyword)

        if not results:
            print("\nNo matching flights found.")
            pause()
            return

        print()
        print(
            f"{'Flight':<10}"
            f"{'Origin':<18}"
            f"{'Destination':<18}"
            f"{'Departure':<20}"
            f"{'Price':>12}"
        )
        print("-" * 80)

        for flight in results:
            self.show_flight(flight)

        pause()

    # -------------------------
    # SEAT MAP
    # -------------------------

    def show_seats(self, flight):
        print(f"\nSeat map for {flight.number}")
        print("O = Available   X = Occupied\n")

        seats = list(flight.seats.items())

        for index in range(0, len(seats), 6):
            row = seats[index:index + 6]

            print(
                f"{index // 6 + 1:>3} {flight.cabin_for_seat(row[0][0]).value[:3]} "
                + " ".join(
                    f"{seat}:{'O' if passenger is None else 'X'}"
                    for seat, passenger in row
                )
            )

    # -------------------------
    # INSURANCE
    # -------------------------

    def insurance_options(self):
        print("\n" + "-" * 50)
        print("MEDICAL / TRAVEL INSURANCE")
        print("-" * 50)

        print("\nDo you already have medical/travel insurance?")
        print("1. Yes, I already have insurance")
        print("2. No, I do not have insurance")

        choice = ask_int("Select option: ", 1, 2)

        if choice == 1:
            print("\nYour existing insurance will be recorded.")
            return InsuranceTier.EXISTING.value, 0

        print("\nYou do not currently have insurance.")

        print("\nWould you like to secure insurance now?")
        print("1. Yes")
        print("2. No")

        choice = ask_int("Select option: ", 1, 2)

        if choice == 2:
            print("\nNo insurance will be added.")
            return InsuranceTier.NONE.value, 0

        print("\nAvailable insurance options:")
        print("1. Basic Medical           - ₦4,500")
        print("2. Premium Comprehensive   - ₦15,000")

        choice = ask_int("Select insurance: ", 1, 2)

        if choice == 1:
            print("\nBasic Medical insurance selected.")
            return InsuranceTier.BASIC_MEDICAL.value, 4500

        print("\nPremium Comprehensive insurance selected.")
        return InsuranceTier.PREMIUM_COMPREHENSIVE.value, 15000

    # -------------------------
    # BOOK FLIGHT
    # -------------------------

    def book_flight(self):
        self.header("BOOK FLIGHT")

        if not self.system.flights:
            print("There are no flights available.")
            pause()
            return

        passport = ask("Passenger passport number: ").upper()

        try:
            passenger = self.system.get_passenger(passport)
        except AirlineError as error:
            print(f"\nError: {error}")
            print("Please register the passenger first.")
            pause()
            return

        flight_number = ask("Flight number: ").upper()

        try:
            flight = self.system.get_flight(flight_number)
        except AirlineError as error:
            print(f"\nError: {error}")
            pause()
            return

        if flight.is_full():
            print("\nThis flight is full.")
            pause()
            return

        print("\nFlight Details")
        print("-" * 50)
        print(f"Flight:       {flight.number}")
        print(f"Route:        {flight.origin} -> {flight.destination}")
        print(f"Departure:    {flight.departure}")
        print(f"Arrival:      {flight.arrival}")
        print(f"Aircraft:     {flight.aircraft_type}")
        print(f"Seats left:   {flight.available_count()}")

        print("\nTravel class")
        print("1. Economy")
        print(
            f"   {money(flight.class_price(FlightClass.ECONOMY))}"
        )
        print("2. Business")
        print(
            f"   {money(flight.class_price(FlightClass.BUSINESS))}"
        )
        print("3. First")
        print(
            f"   {money(flight.class_price(FlightClass.FIRST))}"
        )

        class_choice = ask_int("Select class: ", 1, 3)

        classes = {
            1: FlightClass.ECONOMY,
            2: FlightClass.BUSINESS,
            3: FlightClass.FIRST
        }

        selected_class = classes[class_choice]

        self.show_seats(flight)

        while True:
            seat = ask("\nSelect seat: ").upper()

            if seat not in flight.seats:
                print("That seat does not exist.")
                continue

            if flight.seats[seat] is not None:
                print("That seat is occupied.")
                continue

            if flight.cabin_for_seat(seat) != selected_class:
                print(f"Seat {seat} is in {flight.cabin_for_seat(seat).value}. Pick a {selected_class.value} seat.")
                continue

            break

        insurance, insurance_cost = self.insurance_options()

        quote = self.system.quote(flight.number, selected_class, insurance)
        ticket_price = quote.fare            # dynamic fare (see PricingEngine)
        total = quote.total

        print("\n" + "=" * 50)
        print("BOOKING SUMMARY")
        print("=" * 50)
        print(f"Passenger:       {passenger.name}")
        print(f"Flight:          {flight.number}")
        print(f"Route:           {flight.origin} -> {flight.destination}")
        print(f"Class:           {selected_class.value}")
        print(f"Seat:            {seat}")
        print(f"Ticket:          {money(ticket_price)}")
        print(f"Insurance:       {insurance}")
        print(f"Insurance cost:  {money(insurance_cost)}")
        print(f"TOTAL:           {money(total)}")

        print("\nConfirm booking?")
        print("1. Confirm")
        print("2. Cancel")

        confirm = ask_int("Select option: ", 1, 2)

        if confirm == 2:
            print("\nBooking cancelled by user.")
            pause()
            return

        try:
            booking = self.system.create_booking(
                passport=passport,
                flight_number=flight.number,
                flight_class=selected_class,
                seat=seat,
                insurance=insurance,
                insurance_cost=insurance_cost
            )

            print("\n" + "=" * 50)
            print("BOOKING CONFIRMED")
            print("=" * 50)
            print(f"Booking ID: {booking.booking_id}")
            print(f"Passenger:  {passenger.name}")
            print(f"Flight:     {flight.number}")
            print(f"Seat:       {seat}")
            print(f"Class:      {selected_class.value}")
            print(f"Insurance:  {insurance}")
            print(f"Total:      {money(booking.total_cost)}")
            print(f"Created:    {booking.created_at}")

        except AirlineError as error:
            print(f"\nBooking failed: {error}")

        pause()

    # -------------------------
    # VIEW BOOKING
    # -------------------------

    def view_booking(self):
        self.header("VIEW BOOKING")

        booking_id = ask("Booking ID: ").upper()

        try:
            booking = self.system.get_booking(booking_id)
        except AirlineError as error:
            print(f"\nError: {error}")
            pause()
            return

        passenger = booking.passenger
        flight = booking.flight

        print("\n" + "=" * 55)
        print("BOOKING INFORMATION")
        print("=" * 55)
        print(f"Booking ID:   {booking.booking_id}")
        print(f"Status:       {booking.status}")
        print(f"Passenger:    {passenger.name}")
        print(f"Passport:     {passenger.passport}")
        print(f"Phone:        {passenger.phone}")
        print(f"Email:        {passenger.email}")
        print(f"Flight:       {flight.number}")
        print(f"Route:        {flight.origin} -> {flight.destination}")
        print(f"Departure:    {flight.departure}")
        print(f"Arrival:      {flight.arrival}")
        print(f"Class:        {booking.flight_class}")
        print(f"Seat:         {booking.seat}")
        print(f"Ticket:       {money(booking.ticket_price)}")
        print(f"Insurance:    {booking.insurance}")
        print(f"Insurance:    {money(booking.insurance_cost)}")
        print(f"Total:        {money(booking.total_cost)}")
        print(f"Created:      {booking.created_at}")

        pause()

    # -------------------------
    # CANCEL BOOKING
    # -------------------------

    def cancel_booking(self):
        self.header("CANCEL BOOKING")

        booking_id = ask("Booking ID: ").upper()

        try:
            booking = self.system.get_booking(booking_id)
        except AirlineError as error:
            print(f"\nError: {error}")
            pause()
            return

        print(f"\nPassenger: {booking.passenger.name}")
        print(f"Flight: {booking.flight.number}")
        print(f"Seat: {booking.seat}")
        print(f"Amount: {money(booking.total_cost)}")

        print("\nAre you sure you want to cancel this booking?")
        print("1. Yes")
        print("2. No")

        choice = ask_int("Select option: ", 1, 2)

        if choice == 2:
            print("\nCancellation aborted.")
            pause()
            return

        try:
            note = self.system.cancel_booking(booking_id)
            print("\nBooking cancelled successfully.")
            print(f"Refund: {money(booking.refund_amount)} ({note})")
            print(f"Seat {booking.seat} is now available.")
        except AirlineError as error:
            print(f"\nError: {error}")

        pause()

    # -------------------------
    # ADD FLIGHT
    # -------------------------

    def add_flight(self):
        self.header("ADD FLIGHT")

        number = ask("Flight number: ").upper()

        if number in self.system.flights:
            print("Flight already exists.")
            pause()
            return

        origin = ask("Origin: ")
        destination = ask("Destination: ")
        departure = ask("Departure date/time: ")
        arrival = ask("Arrival date/time: ")
        price = ask_float("Base ticket price: ", 0)
        capacity = ask_int("Passenger capacity: ", 6, 1000)
        aircraft = ask("Aircraft type: ")

        flight = Flight(
            number,
            origin,
            destination,
            departure,
            arrival,
            price,
            capacity,
            aircraft
        )

        try:
            self.system.add_flight(flight)   # validates dates, price, capacity
            print("\nFlight added successfully.")
        except AirlineError as error:
            print(f"\nError: {error}")

        pause()

    # -------------------------
    # REMOVE FLIGHT
    # -------------------------

    def remove_flight(self):
        self.header("REMOVE FLIGHT")

        number = ask("Flight number: ").upper()

        try:
            self.system.remove_flight(number)
            print("\nFlight removed successfully.")
        except AirlineError as error:
            print(f"\nError: {error}")

        pause()

    # -------------------------
    # PASSENGER INFORMATION
    # -------------------------

    def passenger_details(self):
        self.header("PASSENGER INFORMATION")

        passport = ask("Passport number: ").upper()

        try:
            passenger = self.system.get_passenger(passport)
        except AirlineError as error:
            print(f"\nError: {error}")
            pause()
            return

        print(f"\nName:       {passenger.name}")
        print(f"Passport:   {passenger.passport}")
        print(f"Age:        {passenger.age}")
        print(f"Phone:      {passenger.phone}")
        print(f"Email:      {passenger.email}")
        print(f"Miles:      {passenger.miles}")

        print("\nBooking History:")

        if not passenger.history:
            print("No bookings.")
        else:
            for booking_id in passenger.history:
                booking = self.system.bookings.get(booking_id)

                if booking:
                    print(
                        f"- {booking.booking_id} | "
                        f"{booking.flight.number} | "
                        f"{booking.status}"
                    )

        pause()

    # -------------------------
    # AUDIT
    # -------------------------

    def audit(self):
        self.header("SYSTEM AUDIT")

        confirmed = [
            booking for booking in self.system.bookings.values()
            if booking.status == "Confirmed"
        ]

        cancelled = [
            booking for booking in self.system.bookings.values()
            if booking.status == "Cancelled"
        ]

        revenue = sum(
            booking.total_cost
            for booking in confirmed
        )

        print(f"Total flights:       {len(self.system.flights)}")
        print(f"Total passengers:    {len(self.system.passengers)}")
        print(f"Total bookings:      {len(self.system.bookings)}")
        print(f"Confirmed bookings:  {len(confirmed)}")
        print(f"Cancelled bookings:  {len(cancelled)}")
        print(f"Total revenue:       {money(revenue)}")

        print("\nFlight occupancy:")

        for flight in self.system.flights.values():
            occupied = flight.capacity - flight.available_count()
            percentage = (
                occupied / flight.capacity * 100
                if flight.capacity else 0
            )

            print(
                f"{flight.number}: "
                f"{occupied}/{flight.capacity} "
                f"({percentage:.1f}%)"
            )

        pause()

    # -------------------------
    # MAIN MENU
    # -------------------------

    def run(self):
        while True:
            self.header("AIRLINE FLIGHT MANAGEMENT SYSTEM")

            print("1. Register Passenger")
            print("2. List Flights")
            print("3. Search Flights")
            print("4. Book Flight")
            print("5. View Booking")
            print("6. Cancel Booking")
            print("7. Passenger Information")
            print("8. System Audit")
            print("9. Add Flight")
            print("10. Remove Flight")
            print("11. Exit")

            choice = ask_int("\nSelect an option: ", 1, 11)

            if choice == 1:
                self.register_passenger()
            elif choice == 2:
                self.list_flights()
            elif choice == 3:
                self.search_flights()
            elif choice == 4:
                self.book_flight()
            elif choice == 5:
                self.view_booking()
            elif choice == 6:
                self.cancel_booking()
            elif choice == 7:
                self.passenger_details()
            elif choice == 8:
                self.audit()
            elif choice == 9:
                self.add_flight()
            elif choice == 10:
                self.remove_flight()
            elif choice == 11:
                self.system.save()
                print("\nDatabase saved.")
                print("Thank you for using the Airline Flight Management System.")
                break


def main():
    from .services import storage_from_url
    from .services.airline_system import AirlineSystem

    url = os.environ.get("DATABASE_URL", "sqlite:///data/flyte.db")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    system = AirlineSystem(storage=storage_from_url(url, base_dir))
    system.load()
    system.add_sample_flights()
    ConsoleUI(system).run()


if __name__ == "__main__":
    main()
