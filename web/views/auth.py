"""Sign up, log in, log out."""

from urllib.parse import urlparse

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from airline.errors import AirlineError
from airline.utils import passport_valid, phone_valid

from ..security import Auth
from .base import BaseView

bp = Blueprint("auth", __name__)


def safe_next(target, fallback):
    """Only allow same-site relative redirects (no open redirects)."""
    if target and urlparse(target).netloc == "" and target.startswith("/") and not target.startswith("//"):
        return target
    return fallback


class LoginView(BaseView):
    def get(self):
        if self.user:
            return redirect(url_for("account.trips"))
        return render_template("auth/login.html", next=request.args.get("next", ""))

    def post(self):
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        throttle = current_app.extensions["throttle"]
        key = f"{request.remote_addr}|{email}"
        if throttle.blocked(key):
            return render_template("auth/login.html", error="Too many attempts. Wait 10 minutes and try again.",
                                   email=email), 429
        try:
            user = self.system.authenticate(email, password)
        except AirlineError as error:
            throttle.fail(key)
            return render_template("auth/login.html", error=error.message, email=email,
                                   next=request.form.get("next", "")), 401
        throttle.reset(key)
        Auth.login(user)
        fallback = url_for("admin.dashboard") if user.is_admin else url_for("account.trips")
        return redirect(safe_next(request.form.get("next"), fallback))


class SignupView(BaseView):
    FIELDS = ("name", "email", "passport", "age", "phone")

    def get(self):
        return render_template("auth/signup.html", form={}, next=request.args.get("next", ""))

    def post(self):
        form = {k: request.form.get(k, "").strip() for k in self.FIELDS}
        form["passport"] = form["passport"].upper().replace(" ", "")
        errors = self.validate(form)
        if not errors:
            try:
                user = self.system.register_user(
                    form["email"], request.form.get("password", ""), name=form["name"], passport=form["passport"],
                    age=int(form["age"]), phone=form["phone"],
                )
                Auth.login(user)
                return redirect(safe_next(request.form.get("next"), url_for("public.home")))
            except AirlineError as error:
                errors["form"] = error.message
        return render_template("auth/signup.html", form=form, errors=errors, next=request.form.get("next", "")), 400

    @staticmethod
    def validate(form):
        errors = {}
        if len(form["name"].split()) < 2:
            errors["name"] = "Enter your full name as it appears on your passport."
        if not passport_valid(form["passport"]):
            errors["passport"] = "Passport numbers are 6–12 letters and digits."
        if not form["age"].isdigit() or not 1 <= int(form["age"]) <= 120:
            errors["age"] = "Enter an age between 1 and 120."
        if not phone_valid(form["phone"]):
            errors["phone"] = "Enter a phone number like +234 803 000 0000."
        return errors


class LogoutView(BaseView):
    def post(self):
        Auth.logout()
        return redirect(url_for("public.home"))


bp.add_url_rule("/login", view_func=LoginView.as_view("login"))
bp.add_url_rule("/signup", view_func=SignupView.as_view("signup"))
bp.add_url_rule("/logout", view_func=LogoutView.as_view("logout"))
