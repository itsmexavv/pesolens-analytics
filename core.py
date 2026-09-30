"""Small reusable infrastructure for local portfolio demonstrations."""
import csv
import io
import sqlite3
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


class APIError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self, schema, seed):
        with self.connect() as conn:
            conn.executescript(schema)
            conn.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY)")
            if not conn.execute("SELECT 1 FROM app_meta WHERE key='seeded'").fetchone():
                seed(conn)
                conn.execute("INSERT INTO app_meta VALUES ('seeded')")


def rows(cursor):
    return [dict(row) for row in cursor.fetchall()]


def text(value, label, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise APIError(f"{label} must contain 1–{limit} characters.")
    return value.strip()


def integer(value, label, minimum=0, maximum=1_000_000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise APIError(f"{label} must be a whole number from {minimum} to {maximum}.")
    return value


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 1_000_000:
            raise InvalidOperation
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise InvalidOperation
        return int(cents)
    except (InvalidOperation, ValueError):
        raise APIError("Amount must be between 0 and 1,000,000 with at most two decimal places.")


def iso_date(value):
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise APIError("Date must be a valid YYYY-MM-DD date.")


def csv_text(columns, records):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    for record in records:
        # Prevent spreadsheet formula execution when exports are opened in Excel.
        writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v for v in record])
    return output.getvalue()
