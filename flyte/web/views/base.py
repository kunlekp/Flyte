"""Shared base classes for class-based views."""

from flask import current_app, g, jsonify
from flask.views import MethodView

from airline.utils import now


class BaseView(MethodView):
    """Gives every view typed access to the domain services."""

    @property
    def system(self):
        return current_app.extensions["airline"]

    @property
    def analytics(self):
        return current_app.extensions["analytics"]

    @property
    def user(self):
        return g.get("user")

    @property
    def passenger(self):
        return g.get("passenger")

    @staticmethod
    def now():
        return now()


class JsonView(BaseView):
    @staticmethod
    def ok(payload=None, http_status=200, **extra):
        body = dict(payload or {})
        body.update(extra)
        return jsonify(body), http_status

    @staticmethod
    def fail(message, status=400):
        return jsonify(error=message), status
