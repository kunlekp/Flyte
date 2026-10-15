"""Flask application factory.

``FlyteApp`` wires the OOP domain (AirlineSystem + AnalyticsEngine) into
Flask: storage selection, first-run data, security, filters and blueprints.
"""

import logging
import os

from flask import Flask, jsonify, render_template, request

from airline.analytics import AnalyticsEngine
from airline.errors import AirlineError
from airline.seed import DemoDataSeeder
from airline.utils import utc_offset
from airline.services import (
    AirlineSystem, JsonStorage, LogNotifier, MockPaymentGateway, NotificationService, SmtpNotifier, storage_from_url,
)

from .config import get_config
from .formatting import TemplateFilters
from .security import Auth, CSRFGuard, LoginThrottle, SecurityHeaders

log = logging.getLogger("flyte")


class FlyteApp:
    """Builds and configures the Flask app around one AirlineSystem."""

    def __init__(self, config=None):
        self.config = config or get_config()
        self.app = Flask(__name__, static_folder="static", template_folder="templates")
        self.app.config.from_object(self.config)

    # ------------------------------------------------------------------ build
    def build(self):
        self._check_production_settings()
        system = self._build_system()
        self._first_run(system)
        self.app.extensions["airline"] = system
        self.app.extensions["analytics"] = AnalyticsEngine(system)
        self.app.extensions["throttle"] = LoginThrottle()

        Auth(self.app)
        CSRFGuard(self.app)
        SecurityHeaders(self.app)
        TemplateFilters.register(self.app)
        self._register_blueprints()
        self._register_error_handlers()
        self.app.jinja_env.globals["asset_version"] = "1.2.0"
        self.app.jinja_env.globals["utc_offset"] = utc_offset
        return self.app

    def _check_production_settings(self):
        """Refuse to start a production server with settings that would lose
        sessions or leak demo credentials."""
        if not self.app.config.get("IS_PRODUCTION"):
            return
        problems = []
        if not os.environ.get("SECRET_KEY") or len(os.environ["SECRET_KEY"]) < 32:
            problems.append("SECRET_KEY must be set to a random string of 32+ characters")
        if not (self.app.config["ADMIN_EMAIL"] and self.app.config["ADMIN_PASSWORD"]) and not self.app.config["SEED_DEMO"]:
            problems.append("set ADMIN_EMAIL and ADMIN_PASSWORD so you can log in to the ops console")
        if problems:
            raise RuntimeError("Production settings incomplete: " + "; ".join(problems))

    def _build_system(self):
        cfg = self.app.config
        if cfg["SMTP_HOST"]:
            notifier = SmtpNotifier(cfg["SMTP_HOST"], cfg["SMTP_PORT"], cfg["SMTP_USER"], cfg["SMTP_PASSWORD"], cfg["MAIL_FROM"])
        else:
            notifier = LogNotifier(cfg["OUTBOX_PATH"])
        system = AirlineSystem(
            storage=storage_from_url(cfg["DATABASE_URL"], cfg["BASE_DIR"]),
            payments=MockPaymentGateway(),      # swap for a Paystack gateway in production
            notifications=NotificationService(notifier),
        )
        system.load()
        return system

    def _first_run(self, system):
        cfg = self.app.config
        if system.flights or system.users:
            if cfg["SEED_DEMO"] and all(f.carrier.code == "XX" for f in system.flights.values()):
                print(" * Your database is from an older version (no airlines). "
                      "Run `python manage.py reset-demo` to load the new demo data.", flush=True)
        elif cfg["LEGACY_JSON"] and os.path.exists(cfg["LEGACY_JSON"]):
            log.info("Importing legacy console database %s", cfg["LEGACY_JSON"])
            system.load_snapshot(JsonStorage(cfg["LEGACY_JSON"]).load())
            system.save()
        elif cfg["SEED_DEMO"]:
            log.info("Seeding demo data (first run only)…")
            print(" * Seeding demo data – first run takes ~10 seconds…", flush=True)
            stats = DemoDataSeeder(system).run()
            print(f" * Demo data ready: {stats}", flush=True)
        else:
            system.add_sample_flights()
        if cfg["ADMIN_EMAIL"] and cfg["ADMIN_PASSWORD"]:
            system.create_admin(cfg["ADMIN_EMAIL"], cfg["ADMIN_PASSWORD"])

    def _register_blueprints(self):
        from .views import account, admin, api, auth, booking, public
        for module in (public, auth, booking, account, admin, api):
            self.app.register_blueprint(module.bp)

    def _register_error_handlers(self):
        app = self.app

        def wants_json():
            return request.path.startswith("/api/") or request.is_json

        @app.errorhandler(AirlineError)
        def domain_error(error):
            if wants_json():
                return jsonify(error=error.message), error.http_status
            return render_template("errors/error.html", code=error.http_status, message=error.message), error.http_status

        @app.errorhandler(ValueError)
        def bad_value(error):
            if wants_json():
                return jsonify(error=str(error)), 400
            return render_template("errors/error.html", code=400, message=str(error)), 400

        for code, message in ((400, "That request didn't look right."), (403, "This area is for Flyte staff."),
                              (404, "We couldn't find that page. It may have moved or the flight was removed."),
                              (500, "Something broke on our side. Try again in a moment.")):
            def handler(error, code=code, message=message):
                text = getattr(error, "description", None) if code == 400 else message
                if wants_json():
                    return jsonify(error=text or message), code
                return render_template("errors/error.html", code=code, message=text or message), code
            app.register_error_handler(code, handler)


def create_app(config=None):
    return FlyteApp(config).build()
