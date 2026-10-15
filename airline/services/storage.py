"""Persistence backends.

``StorageBackend`` is an abstract base class; ``JsonStorage`` (what the
console app used) and ``SqliteStorage`` (recommended for the web) are two
interchangeable implementations – classic polymorphism. ``AirlineSystem``
only ever talks to the abstract interface.
"""

import json
import os
import sqlite3
import tempfile
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager

COLLECTIONS = ("flights", "passengers", "bookings", "users")


class StorageBackend(ABC):
    def __init__(self):
        self._lock = threading.RLock()
        self._batch_depth = 0

    @abstractmethod
    def load(self):
        """Return {'meta': {...}, 'flights': {...}, 'passengers': {...}, ...}."""

    @abstractmethod
    def upsert(self, collection, key, data):
        ...

    @abstractmethod
    def delete(self, collection, key):
        ...

    @abstractmethod
    def set_meta(self, key, value):
        ...

    @abstractmethod
    def _flush(self):
        """Commit pending writes (called when the outermost batch ends)."""

    @contextmanager
    def batch(self):
        """Group many writes into one commit – used by seeding and save()."""
        with self._lock:
            self._batch_depth += 1
            try:
                yield self
            finally:
                self._batch_depth -= 1
                if self._batch_depth == 0:
                    self._flush()

    def _maybe_flush(self):
        if self._batch_depth == 0:
            self._flush()

    def is_empty(self):
        snapshot = self.load()
        return not any(snapshot.get(name) for name in COLLECTIONS)

    def describe(self):
        return type(self).__name__


class JsonStorage(StorageBackend):
    """Single JSON file, written atomically (temp file + rename)."""

    def __init__(self, path):
        super().__init__()
        self.path = path
        self._data = None

    def _ensure_loaded(self):
        if self._data is not None:
            return
        self._data = {"meta": {}, **{name: {} for name in COLLECTIONS}}
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as file:
                raw = json.load(file)
            # The original console DB stored booking_number at the top level.
            if "booking_number" in raw:
                self._data["meta"]["booking_number"] = raw["booking_number"]
            self._data["meta"].update(raw.get("meta", {}))
            for name in COLLECTIONS:
                if name in raw:
                    self._data[name] = raw[name]

    def load(self):
        with self._lock:
            self._ensure_loaded()
            return json.loads(json.dumps(self._data))   # defensive deep copy

    def upsert(self, collection, key, data):
        with self._lock:
            self._ensure_loaded()
            self._data.setdefault(collection, {})[key] = data
            self._maybe_flush()

    def delete(self, collection, key):
        with self._lock:
            self._ensure_loaded()
            self._data.get(collection, {}).pop(key, None)
            self._maybe_flush()

    def set_meta(self, key, value):
        with self._lock:
            self._ensure_loaded()
            self._data["meta"][key] = value
            self._maybe_flush()

    def _flush(self):
        if self._data is None:
            return
        folder = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder, exist_ok=True)
        payload = dict(self._data)
        payload["booking_number"] = self._data["meta"].get("booking_number", 1000)
        fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
        os.replace(tmp, self.path)


class SqliteStorage(StorageBackend):
    """Document store on SQLite – one row per entity, JSON payload."""

    def __init__(self, path):
        super().__init__()
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS documents ("
            " collection TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL,"
            " PRIMARY KEY (collection, key))"
        )
        self._conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._conn.commit()

    def load(self):
        with self._lock:
            snapshot = {"meta": {}, **{name: {} for name in COLLECTIONS}}
            for collection, key, data in self._conn.execute("SELECT collection, key, data FROM documents"):
                snapshot.setdefault(collection, {})[key] = json.loads(data)
            for key, value in self._conn.execute("SELECT key, value FROM meta"):
                snapshot["meta"][key] = json.loads(value)
            return snapshot

    def upsert(self, collection, key, data):
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents(collection, key, data) VALUES (?, ?, ?) "
                "ON CONFLICT(collection, key) DO UPDATE SET data = excluded.data",
                (collection, key, json.dumps(data)),
            )
            self._maybe_flush()

    def delete(self, collection, key):
        with self._lock:
            self._conn.execute("DELETE FROM documents WHERE collection = ? AND key = ?", (collection, key))
            self._maybe_flush()

    def set_meta(self, key, value):
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )
            self._maybe_flush()

    def _flush(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def describe(self):
        return f"SQLite ({os.path.basename(self.path)})"


def storage_from_url(url, base_dir=None):
    """'sqlite:///data/flyte.db' (relative) or 'sqlite:////abs/path.db',
    or 'json:///data/airline_db.json'. Relative paths are resolved against
    `base_dir` (the project folder) so the app works from any working dir."""
    scheme, _, path = url.partition("://")
    path = path.lstrip("/") if not path.startswith("//") else path[1:]
    default = {"sqlite": "data/flyte.db", "json": "data/airline_db.json"}.get(scheme)
    path = path or default
    if path and path != ":memory:" and base_dir and not os.path.isabs(path):
        path = os.path.join(base_dir, path)
    if scheme == "sqlite":
        return SqliteStorage(path)
    if scheme == "json":
        return JsonStorage(path)
    raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme!r}")
