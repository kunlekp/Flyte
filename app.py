"""Flyte – run the web app locally.

    python app.py            → http://127.0.0.1:5000
    python -m airline.cli    → the original console interface (same database)
"""

import os

try:                                   # optional: read settings from .env
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from web import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1" and os.environ.get("APP_ENV") != "production",
    )
