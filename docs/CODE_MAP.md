# Flyte code map: which file does what

A study guide to the project. Use it to answer two questions: *"where is the thing I see on screen?"* and
*"how do the files connect?"*

---

## 1. Find anything in 10 seconds (VS Code)

| You want to find… | Do this |
|---|---|
| Some **words you can see on a page** (a heading, a button label) | **Ctrl+Shift+F** (search all files) and type a few of those exact words. They almost always live in a file under `web/templates/`. |
| A **file by name** | **Ctrl+P**, then type part of the name, e.g. `home.html`. |
| Where a **class or method is defined** | Click on its name and press **F12** (Go to Definition). |
| Every place a class or method is **used** | Click on its name and press **Shift+F12** (Find All References). |

Example: the headline. Ctrl+Shift+F → `without the drama` → `web/templates/home.html`, line 8:

```html
<h1>Fly without the drama.</h1>
```

Change the words between `<h1>` and `</h1>`, save, then refresh the browser.

---

## 2. The five layers: what kind of change goes where

Every page you see is assembled from five layers. Decide which layer your change belongs to and you'll know
which folder to open.

| Layer | Folder | Language | Change this when you want to change… |
|---|---|---|---|
| **Words & layout** | `web/templates/` | HTML + Jinja (`{{ }}`, `{% %}`) | text, headings, buttons, what appears where on a page |
| **Look** | `web/static/css/app.css` | CSS | colours, fonts, spacing, animations |
| **On-page behaviour** | `web/static/js/` | JavaScript | things that react without reloading: seat map, booking steps, charts, the route map |
| **URLs** | `web/views/` | Python (Flask) | which page a URL shows, and what data it gets from the airline classes |
| **Airline rules** (the OOP core) | `airline/` | Python | prices, bag fees, refunds, discounts, seats, airlines, analytics: anything the airline *does* |

How they connect:

```
Browser asks for /flights
   → web/views/public.py      FlightsView.get() asks AirlineSystem for the data
   → airline/…                the classes work out flights, fares, recommendation
   → web/templates/flights.html   turns that data into HTML (using partials/macros.html)
   → web/static/css/app.css   makes it look right
   → web/static/js/…          adds the moving parts
```

---

## 3. Page by page

Each row: the URL you visit → the Python class that handles it → the template that draws it → the
JavaScript that runs on it → the airline classes it relies on.

### Public pages: `web/views/public.py`

| URL | What you see | View class | Template | JavaScript | Airline classes used |
|---|---|---|---|---|---|
| `/` | Home: headline, route map, "Leaving soon" cards | `HomeView` | `home.html` | `routemap.js` | `AirlineSystem.upcoming_flights`, `AIRPORTS`, `PricingEngine` (via `FlightCardBuilder`) |
| `/flights` | Search results (one-way), airline badges, "Our pick" | `FlightsView` | `flights.html` | `search.js` (via `app.js`) | `search_flights`, `AirlineRecommender`, `PricingEngine` |
| `/flights?trip=return` or `multicity` | One list per leg, sticky trip total | `FlightsView` → `TripSearch` | `trip_results.html` | `triplanner.js` | `ItineraryPlanner`, `TripType`, `AirlineRecommender` |
| `/flights/<number>` | Single-flight booking: cabin → seat → bags → cover → pay | `FlightDetailView` | `flight.html` | `booking.js`, `seatmap.js` | `Flight.seat_map`, `quote`, `FareAdvisor`, `BaggagePolicy` |
| `/trip` | Checkout for a return / multi-city trip | `TripCheckoutView` | `trip_checkout.html` | `tripbooking.js`, `seatmap.js` | `quote_trip`, `Itinerary` |
| `/manage` | Look up a booking by reference + email | `ManageBookingView` | `manage.html` | — | `find_booking` |

### Booking actions: `web/views/booking.py` (no page; called by the JavaScript)

| URL | Called from | View class | Airline method |
|---|---|---|---|
| `POST /book/<number>` | `booking.js` (Pay button) | `CheckoutView` | `AirlineSystem.book_and_pay()` |
| `POST /book-trip` | `tripbooking.js` (Pay button) | `TripCheckoutApi` | `AirlineSystem.book_trip()` |

### Logging in: `web/views/auth.py`

| URL | View class | Template | Airline method |
|---|---|---|---|
| `/login` | `LoginView` | `auth/login.html` | `authenticate()`, plus `LoginThrottle` from `web/security.py` |
| `/signup` | `SignupView` | `auth/signup.html` | `register_user()` |
| `/logout` | `LogoutView` | — | — |

### My account: `web/views/account.py`

| URL | What you see | View class | Template | JavaScript |
|---|---|---|---|---|
| `/trips` | List of my bookings and trips | `TripsView` | `account/trips.html` | — |
| `/trips/<booking_id>` | Boarding pass, QR code, check-in, cancel | `TripView` | `account/trip.html` | `trip.js` (confetti) |
| `/trips/trip/<trip_id>` | A whole return / multi-city trip | `ItineraryView` | `account/itinerary.html` | `trip.js` |
| `POST …/check-in` | Check-in button | `CheckInView` | — | — |
| `POST …/cancel` | Cancel button | `CancelView` | — | — |
| `/profile` | Miles, loyalty tier, details | `ProfileView` | `account/profile.html` | — |

`OwnedBookingMixin` (same file) is a small parent class that makes sure you can only open your own bookings.

### Admin (ops console): `web/views/admin.py`, all under `/admin`

| URL | What you see | View class | Template | JavaScript | Airline classes used |
|---|---|---|---|---|---|
| `/admin` | **Network pulse** dashboard | `DashboardView` | `admin/dashboard.html` | `admin.js`, `charts.js` | `AnalyticsEngine.overview()` (fetched from `/api/admin/overview`) |
| `/admin/flights` | Add / delay / cancel flights | `FlightsAdminView`, `FlightActionView` | `admin/flights.html` | — | `add_flight`, `delay_flight`, `cancel_flight` |
| `/admin/bookings` | All bookings | `BookingsAdminView` | `admin/bookings.html` | — | — |
| `/admin/passengers` | All passengers, with spend and trip counts | `PassengersAdminView` | `admin/passengers.html` | — | `AnalyticsEngine.passenger_features()` |
| `/admin/export/<kind>.csv` | CSV download (bookings, flights, anonymised passengers) | `ExportView` | — | — | reads `system.bookings` / `flights` / `passengers` directly |

All admin views inherit from `AdminView`, which blocks anyone who isn't an admin.

### Data API: `web/views/api.py`, all under `/api`, returns JSON for the JavaScript

| URL | Used by | View class |
|---|---|---|
| `/api/flights/<number>/seats` | `seatmap.js` | `SeatMapApi` |
| `/api/flights/<number>/quote` | `booking.js` (live price as you choose) | `QuoteApi` |
| `/api/flights/<number>/advice` | `booking.js` (fare forecast sparkline) | `AdviceApi` |
| `/api/trip/quote` | `tripbooking.js` | `TripQuoteApi` |
| `/api/admin/overview` | `admin.js` | `OverviewApi` |
| `/api/flights`, `/api/airports`, `/api/airlines`, `/api/health` | search / external use / health check | `FlightSearchApi`, `AirportsApi`, `AirlinesApi`, `HealthApi` |

---

## 4. "I want to change…": quick answers

| I want to change… | File | Look for |
|---|---|---|
| The **home headline** or the line under it | `web/templates/home.html` | `<h1>` and `hero__lede` |
| The **browser tab title**, **nav links** or **footer** | `web/templates/base.html` | `<title>`, `<nav`, `<footer` |
| How a **flight card** looks (used on several pages) | `web/templates/partials/macros.html` | `{% macro flight_pass` |
| The **search box** (one-way / return / multi-city) | `web/templates/partials/macros.html` + `web/static/js/search.js` | `{% macro search_ticket` |
| **Colours** (whole site, light and dark) | `web/static/css/app.css` | `:root {` at the top; dark theme a few lines below |
| The **airlines**, their price level, colours, **bag allowance and bag fees** | `airline/models/carrier.py` | `AIRLINES = AirlineDirectory(` |
| The **airports** | `airline/models/airport.py` | `AIRPORTS` |
| The **return-trip discount** (8%) | `airline/enums.py` | `def fare_discount` |
| **Insurance prices** / **loyalty tier thresholds** | `airline/enums.py` | `class InsuranceTier`, `class LoyaltyTier` |
| The **pricing formula** (demand, days to departure, min/max) | `airline/services/pricing.py` | `class PricingEngine` |
| **Refund rules** (90% / 50% / 0%) | `airline/services/pricing.py` | `class RefundPolicy` |
| **Miles earned** | `airline/services/pricing.py` | `class LoyaltyProgram` |
| How **"Our pick"** is chosen (70% price / 30% seats) | `airline/services/recommend.py` | `PRICE_WEIGHT`, `SEATS_WEIGHT` |
| **Minimum connection time** / max legs | `airline/services/itinerary.py` (and `MIN_CONNECTION_MS` in `web/static/js/triplanner.js` to match) | `MIN_CONNECTION`, `MAX_LEGS` |
| **Confirmation email text** | `airline/services/notifier.py` | `class NotificationService` |
| **Demo data** (number of passengers, days, demo logins) | `airline/seed.py` | `class DemoDataSeeder` |
| **Dashboard numbers / charts** | `airline/analytics/engine.py` (numbers) + `web/static/js/admin.js` (drawing) | `def overview` |
| **Settings** (database, secret key, time zone) | `.env` (copy from `.env.example`) and `web/config.py` | `class Config` |

After changing **demo data** or anything stored in the database, run `python manage.py reset-demo` to rebuild
it.

---

## 5. Every file, one line each

```
flyte/
├── app.py                     START HERE: `python app.py` runs the website (calls web.create_app)
├── manage.py                  maintenance: reset-demo, create-admin, stats
├── requirements.txt           Python packages to install
├── .env.example               settings template → copy to .env
│
├── airline/                   ── THE OOP CORE (no web code in here) ──
│   ├── enums.py               fixed choices: FlightClass, InsuranceTier, TripType, LoyaltyTier, statuses
│   ├── errors.py              AirlineError + 12 child errors
│   ├── utils.py               now() in Lagos time, small helpers
│   ├── cli.py                 ConsoleUI: the original text menu (`python -m airline.cli`)
│   ├── seed.py                DemoDataSeeder + Persona: fills the database with demo data
│   ├── models/                the THINGS
│   │   ├── flight.py          Flight: seats, prices per cabin, status, load factor
│   │   ├── passenger.py       Passenger: profile, miles, loyalty tier
│   │   ├── booking.py         Booking: one passenger, one seat, one flight
│   │   ├── itinerary.py       Itinerary: a whole trip (groups Bookings)
│   │   ├── carrier.py         Airline, BaggagePolicy, AirlineDirectory (AIRLINES)
│   │   ├── airport.py         Airport, AirportDirectory (AIRPORTS), distances
│   │   └── user.py            User: login account, password hash, role
│   ├── services/              the JOBS
│   │   ├── airline_system.py  AirlineSystem: the brain; every action is a method here
│   │   ├── pricing.py         PricingEngine, FareQuote, FareAdvisor, RefundPolicy, LoyaltyProgram
│   │   ├── recommend.py       AirlineRecommender ("Our pick")
│   │   ├── itinerary.py       ItineraryPlanner: return / multi-city legs
│   │   ├── payments.py        CardDetails, PaymentGateway (abstract), MockPaymentGateway
│   │   ├── notifier.py        Notifier (abstract), LogNotifier, SmtpNotifier, NotificationService
│   │   └── storage.py         StorageBackend (abstract), JsonStorage, SqliteStorage
│   └── analytics/             the DATA SCIENCE
│       ├── engine.py          AnalyticsEngine: DataFrames, KPIs, every dashboard number
│       ├── forecasting.py     Forecaster (abstract), SeasonalTrendForecaster
│       └── segmentation.py    KMeans (from scratch), PassengerSegmenter
│
├── web/                       ── THE WEBSITE (calls into airline/) ──
│   ├── __init__.py            FlyteApp: builds the app, creates the one AirlineSystem
│   ├── config.py              settings classes (dev / production / test)
│   ├── security.py            Auth, CSRFGuard, LoginThrottle, SecurityHeaders
│   ├── formatting.py          template filters: money (₦), dates, durations
│   ├── views/                 one class per page (see section 3)
│   │   ├── base.py            BaseView, JsonView: parents of every view
│   │   ├── public.py          home, search, flight, trip checkout, manage
│   │   ├── booking.py         the Pay buttons
│   │   ├── auth.py            login, signup, logout
│   │   ├── account.py         my trips, boarding pass, check-in, cancel, profile
│   │   ├── admin.py           ops console + Network pulse
│   │   └── api.py             JSON for the JavaScript
│   ├── templates/             the HTML (words and layout)
│   │   ├── base.html          the frame every page sits in: <head>, nav, footer
│   │   ├── partials/macros.html   reusable pieces: flight card, search box, airline badge
│   │   ├── home.html, flights.html, flight.html, trip_results.html, trip_checkout.html, manage.html
│   │   ├── account/           trips.html, trip.html, itinerary.html, profile.html
│   │   ├── admin/             _layout.html, dashboard.html, flights.html, bookings.html, passengers.html
│   │   ├── auth/              login.html, signup.html
│   │   └── errors/error.html
│   └── static/
│       ├── css/app.css        all styling, in labelled sections (/* === hero === */ etc.)
│       ├── img/favicon.svg
│       └── js/
│           ├── app.js         every page: theme toggle, nav, toasts, counters (imports search.js)
│           ├── theme.js       sets light/dark before the page paints
│           ├── lib.js         shared helpers: Api, money format, confetti
│           ├── search.js      search box: trip-type tabs, multi-city rows
│           ├── routemap.js    RouteMap: the home page "Live network" map
│           ├── seatmap.js     SeatMap, FareSparkline (used by both checkouts)
│           ├── booking.js     single-flight checkout steps
│           ├── triplanner.js  TripPlanner: choose a flight per leg
│           ├── tripbooking.js trip checkout steps
│           ├── trip.js        confetti after booking
│           ├── charts.js      TimeChart, BarChart, Heatmap (dashboard charts)
│           └── admin.js       Network pulse dashboard
│
├── tests/                     33 automated tests (`python -m unittest discover -s tests -v`)
├── docs/                      RUNNING, DEPLOYMENT, GITHUB_AND_PORTFOLIO, this map, the slides
├── portfolio/                 portfolio website template + profile README
├── deploy/, Dockerfile, Procfile, render.yaml   for putting it online
└── .vscode/, .github/         editor settings and the GitHub test workflow
```

---

## 6. Seeing your change

| You changed… | To see it |
|---|---|
| A template (`.html`) | Save, then refresh the browser. |
| CSS or JavaScript | Save, then **hard refresh** (**Ctrl+F5**) because browsers cache these files. |
| Python (`.py`) | The dev server restarts by itself when you save; then refresh. If it crashed, the terminal shows the error. Fix it and run `python app.py` again. |
| Demo data (`seed.py`) | `python manage.py reset-demo`, then restart. |

Then run `python -m unittest discover -s tests -v` (or the VS Code task "Flyte: run tests") to check nothing else broke.
