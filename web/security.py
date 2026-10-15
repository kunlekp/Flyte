"""Web security helpers: sessions/auth, CSRF, login throttling, headers."""

import hmac
import secrets
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, current_app, g, jsonify, redirect, request, session, url_for


class Auth:
    """Session-based authentication bound to the AirlineSystem's users."""

    SESSION_KEY = "user_email"

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.extensions["auth"] = self
        app.before_request(self._load_user)
        app.context_processor(lambda: {"current_user": g.get("user"), "current_passenger": g.get("passenger")})

    @staticmethod
    def system():
        return current_app.extensions["airline"]

    def _load_user(self):
        g.user, g.passenger = None, None
        email = session.get(self.SESSION_KEY)
        if email:
            user = self.system().get_user(email)
            if user:
                g.user = user
                g.passenger = self.system().passengers.get(user.passport) if user.passport else None
            else:
                session.pop(self.SESSION_KEY, None)

    @classmethod
    def login(cls, user):
        session.clear()                       # prevent session fixation
        session[cls.SESSION_KEY] = user.email
        session.permanent = True

    @staticmethod
    def logout():
        session.clear()

    @staticmethod
    def login_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not g.get("user"):
                if request.accept_mimetypes.best == "application/json" or request.path.startswith("/api/"):
                    return jsonify(error="Log in to continue."), 401
                return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
            return view(*args, **kwargs)
        return wrapper

    @staticmethod
    def admin_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not g.get("user"):
                return redirect(url_for("auth.login", next=request.path))
            if not g.user.is_admin:
                abort(403)
            return view(*args, **kwargs)
        return wrapper


class CSRFGuard:
    """Synchroniser-token CSRF protection for forms and fetch() calls."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    SESSION_KEY = "_csrf"

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.before_request(self._check)
        app.jinja_env.globals["csrf_token"] = self.token

    def token(self):
        if self.SESSION_KEY not in session:
            session[self.SESSION_KEY] = secrets.token_urlsafe(32)
        return session[self.SESSION_KEY]

    def _check(self):
        if request.method in self.SAFE_METHODS or current_app.config.get("WTF_CSRF_ENABLED") is False:
            return None
        sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        expected = session.get(self.SESSION_KEY, "")
        if not expected or not hmac.compare_digest(sent, expected):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify(error="Your session expired. Refresh the page and try again."), 400
            abort(400, "Your session expired. Refresh the page and try again.")
        return None


class LoginThrottle:
    """In-memory sliding window: max `limit` failures per key per `window` s."""

    def __init__(self, limit=6, window=600):
        self.limit, self.window = limit, window
        self._failures = defaultdict(deque)

    def _prune(self, key):
        queue = self._failures[key]
        while queue and queue[0] < time.time() - self.window:
            queue.popleft()
        return queue

    def blocked(self, key):
        return len(self._prune(key)) >= self.limit

    def fail(self, key):
        self._prune(key).append(time.time())

    def reset(self, key):
        self._failures.pop(key, None)


class SecurityHeaders:
    def __init__(self, app=None):
        if app:
            app.after_request(self.apply)

    @staticmethod
    def apply(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
        )
        return response
