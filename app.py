"""Expense analytics using exact integer money, SQL aggregation and CSV import."""
import csv
import io
import re
from datetime import date
from core import APIError, Database, csv_text, integer, iso_date, money, rows, text

SCHEMA = """CREATE TABLE IF NOT EXISTS transactions (
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
 category TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
 transaction_date TEXT NOT NULL, note TEXT NOT NULL);"""


class Peso:
    def __init__(self, path):
        self.db = Database(path)
        self.db.initialize(SCHEMA, self.seed)

    @staticmethod
    def seed(conn):
        today = date.today().isoformat()
        conn.executemany("INSERT INTO transactions(kind,category,amount_cents,transaction_date,note) VALUES (?,?,?,?,?)", [
            ("income", "Allowance", 600000, today, "Synthetic monthly allowance"),
            ("expense", "Food", 125000, today, "Demo groceries"),
            ("expense", "Transport", 45000, today, "Demo commute"),
            ("expense", "School", 80000, today, "Demo materials")])

    @staticmethod
    def validate(data):
        kind = data.get("kind")
        if kind not in ("income", "expense"):
            raise APIError("Kind must be income or expense.")
        cents = money(data.get("amount"))
        if cents == 0:
            raise APIError("Amount must be greater than zero.")
        note = data.get("note", "")
        if not isinstance(note, str) or len(note) > 300:
            raise APIError("Note must be text with at most 300 characters.")
        return (kind, text(data.get("category"), "Category", 50), cents, iso_date(data.get("date")), note.strip())

    def handle(self, method, path, data, query):
        month = query.get("month", [date.today().strftime("%Y-%m")])[0]
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise APIError("Month must be YYYY-MM.")
        with self.db.connect() as conn:
            if path in ("/transactions", "/export") and method == "GET":
                records = rows(conn.execute("SELECT * FROM transactions WHERE substr(transaction_date,1,7)=? ORDER BY transaction_date DESC,id DESC", (month,)))
                if path == "/export":
                    return (csv_text(["kind", "category", "amount", "date", "note"], [[r["kind"], r["category"], f'{r["amount_cents"]/100:.2f}', r["transaction_date"], r["note"]] for r in records]), "text/csv; charset=utf-8")
                return records
            if path == "/transactions" and method == "POST":
                cursor = conn.execute("INSERT INTO transactions(kind,category,amount_cents,transaction_date,note) VALUES (?,?,?,?,?)", self.validate(data))
                return {"id": cursor.lastrowid}
            if path.startswith("/transactions/") and method == "DELETE":
                try:
                    record_id = int(path.rsplit("/", 1)[-1])
                except ValueError:
                    raise APIError("Transaction ID must be a number.")
                if conn.execute("DELETE FROM transactions WHERE id=?", (record_id,)).rowcount == 0:
                    raise APIError("Transaction not found.", 404)
                return {"deleted": record_id}
            if path == "/summary" and method == "GET":
                totals = {r["kind"]: r["total"] for r in conn.execute("SELECT kind,SUM(amount_cents) AS total FROM transactions WHERE substr(transaction_date,1,7)=? GROUP BY kind", (month,))}
                categories = rows(conn.execute("SELECT category,SUM(amount_cents) AS total FROM transactions WHERE kind='expense' AND substr(transaction_date,1,7)=? GROUP BY category ORDER BY total DESC,category", (month,)))
                income, expense = totals.get("income", 0), totals.get("expense", 0)
                return {"income": income, "expense": expense, "balance": income-expense, "categories": categories, "month": month}
            if path == "/import" and method == "POST":
                source = data.get("csv")
                if not isinstance(source, str) or len(source) > 100_000:
                    raise APIError("CSV must contain at most 100,000 characters.")
                reader = csv.DictReader(io.StringIO(source.lstrip('\ufeff')), strict=True)
                if reader.fieldnames != ["kind", "category", "amount", "date", "note"]:
                    raise APIError("CSV header must be kind,category,amount,date,note in that order.")
                validated = []
                try:
                    for line, record in enumerate(reader, 2):
                        if len(validated) >= 1000:
                            raise APIError("CSV import is limited to 1,000 rows.")
                        if None in record or any(v is None for v in record.values()):
                            raise APIError(f"CSV row {line} has an incorrect number of fields.")
                        try:
                            validated.append(self.validate(record))
                        except APIError as exc:
                            raise APIError(f"CSV row {line}: {exc}")
                except csv.Error:
                    raise APIError("CSV is malformed.")
                if not validated:
                    raise APIError("CSV contains no transactions.")
                conn.executemany("INSERT INTO transactions(kind,category,amount_cents,transaction_date,note) VALUES (?,?,?,?,?)", validated)
                return {"imported": len(validated)}
        raise APIError("Endpoint not found.", 404)
