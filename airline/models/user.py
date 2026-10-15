"""User account – login identity, separate from the Passenger travel profile."""

from werkzeug.security import check_password_hash, generate_password_hash

from ..enums import Role
from ..utils import timestamp


class User:
    MIN_PASSWORD_LENGTH = 8

    def __init__(self, email, password_hash, role=Role.PASSENGER.value,
                 passport=None, display_name="", created_at=None, last_login=None):
        self.email = email.strip().lower()
        self.password_hash = password_hash
        self.role = role
        self.passport = passport          # links to a Passenger profile
        self.display_name = display_name
        self.created_at = created_at or timestamp()
        self.last_login = last_login

    @classmethod
    def create(cls, email, password, **kwargs):
        cls.check_password_strength(password)
        return cls(email, generate_password_hash(password), **kwargs)

    @classmethod
    def check_password_strength(cls, password):
        from ..errors import InvalidDataError
        if len(password or "") < cls.MIN_PASSWORD_LENGTH:
            raise InvalidDataError(f"Use at least {cls.MIN_PASSWORD_LENGTH} characters for your password.")
        if password.isdigit() or password.isalpha():
            raise InvalidDataError("Mix letters and numbers in your password.")

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password or "")

    def set_password(self, password):
        self.check_password_strength(password)
        self.password_hash = generate_password_hash(password)

    @property
    def is_admin(self):
        return self.role == Role.ADMIN.value

    def to_dict(self):
        return {
            "email": self.email,
            "password_hash": self.password_hash,
            "role": self.role,
            "passport": self.passport,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            email=data["email"],
            password_hash=data["password_hash"],
            role=data.get("role", Role.PASSENGER.value),
            passport=data.get("passport"),
            display_name=data.get("display_name", ""),
            created_at=data.get("created_at"),
            last_login=data.get("last_login"),
        )

    def __repr__(self):
        return f"User({self.email}, {self.role})"
