"""Maintenance commands.

    python manage.py reset-demo        wipe the database and reseed demo data
    python manage.py create-admin EMAIL PASSWORD
    python manage.py stats             quick numbers from the database
"""

import argparse
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from airline.analytics import AnalyticsEngine
from airline.seed import DemoDataSeeder
from airline.services import AirlineSystem, storage_from_url

URL = os.environ.get("DATABASE_URL", "sqlite:///data/flyte.db")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def open_system():
    system = AirlineSystem(storage=storage_from_url(URL, BASE_DIR))
    system.load()
    return system


def reset_demo(_):
    storage = storage_from_url(URL, BASE_DIR)
    path = getattr(storage, "path", None)
    if hasattr(storage, "close"):
        storage.close()
    for suffix in ("", "-wal", "-shm"):
        if path and path != ":memory:" and os.path.exists(path + suffix):
            os.remove(path + suffix)
    system = AirlineSystem(storage=storage_from_url(URL, BASE_DIR))
    print("Seeding…", DemoDataSeeder(system).run())


def create_admin(args):
    open_system().create_admin(args.email, args.password)
    print(f"Admin {args.email} ready.")


def stats(_):
    k = AnalyticsEngine(open_system()).kpis()
    for key, value in k.items():
        if isinstance(value, dict):
            print(f"{key:>14}: {value['value']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flyte maintenance")
    sub = parser.add_subparsers(required=True)
    sub.add_parser("reset-demo").set_defaults(func=reset_demo)
    p = sub.add_parser("create-admin")
    p.add_argument("email")
    p.add_argument("password")
    p.set_defaults(func=create_admin)
    sub.add_parser("stats").set_defaults(func=stats)
    args = parser.parse_args()
    args.func(args)
