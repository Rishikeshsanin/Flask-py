from __future__ import annotations

import csv
import io
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from flask import Flask, Response, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
LEGACY_DB_PATH = BASE_DIR / "expense.db"
DEFAULT_DB_PATH = LEGACY_DB_PATH if LEGACY_DB_PATH.exists() else BASE_DIR / "instance" / "expenses.db"
CATEGORIES = (
    "Food",
    "Transport",
    "Shopping",
    "Bills",
    "Health",
    "Education",
    "Entertainment",
    "Travel",
    "Other",
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-expense-tracker-secret")
app.config["DATABASE"] = os.environ.get("DATABASE_PATH", str(DEFAULT_DB_PATH))


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = Path(app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    with app.app_context():
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS expense (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                category TEXT NOT NULL DEFAULT 'Other',
                expense_date TEXT NOT NULL DEFAULT (date('now')),
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Keep old first-year databases working after the glow-up.
        columns = {row["name"] for row in db.execute("PRAGMA table_info(expense)")}
        migrations = {
            "category": "TEXT NOT NULL DEFAULT 'Other'",
            "expense_date": "TEXT NOT NULL DEFAULT ''",
            "notes": "TEXT NOT NULL DEFAULT ''",
            "created_at": "TEXT NOT NULL DEFAULT ''",
        }
        for column, definition in migrations.items():
            if column not in columns:
                db.execute(f"ALTER TABLE expense ADD COLUMN {column} {definition}")

        db.execute(
            "UPDATE expense SET expense_date = date('now') WHERE expense_date IS NULL OR expense_date = ''"
        )
        db.execute(
            "UPDATE expense SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL OR created_at = ''"
        )
        db.commit()


def parse_expense_form() -> tuple[str, float, str, str, str]:
    name = request.form.get("name", "").strip()
    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "Other").strip()
    expense_date = request.form.get("expense_date", "").strip()
    notes = request.form.get("notes", "").strip()

    if not 1 <= len(name) <= 80:
        raise ValueError("Expense name must be between 1 and 80 characters.")

    try:
        amount = round(float(amount_raw), 2)
    except ValueError as exc:
        raise ValueError("Enter a valid amount.") from exc

    if amount <= 0 or amount > 100_000_000:
        raise ValueError("Amount must be greater than zero and within a reasonable range.")

    if category not in CATEGORIES:
        category = "Other"

    try:
        parsed_date = date.fromisoformat(expense_date)
    except ValueError as exc:
        raise ValueError("Choose a valid expense date.") from exc

    if parsed_date > date.today():
        raise ValueError("Expense date cannot be in the future.")

    if len(notes) > 240:
        raise ValueError("Notes must be 240 characters or fewer.")

    return name, amount, category, expense_date, notes


def dashboard_stats(db: sqlite3.Connection) -> dict[str, float | int | str]:
    row = db.execute(
        """
        SELECT
            COALESCE(SUM(amount), 0) AS total,
            COUNT(*) AS count,
            COALESCE(AVG(amount), 0) AS average,
            COALESCE(MAX(amount), 0) AS largest
        FROM expense
        """
    ).fetchone()

    this_month = date.today().strftime("%Y-%m")
    month_total = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expense WHERE substr(expense_date, 1, 7) = ?",
        (this_month,),
    ).fetchone()["total"]

    return {
        "total": float(row["total"]),
        "count": int(row["count"]),
        "average": float(row["average"]),
        "largest": float(row["largest"]),
        "month_total": float(month_total),
    }


@app.route("/")
def home():
    db = get_db()
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "newest").strip()

    where = []
    params: list[str] = []
    if query:
        where.append("(Name LIKE ? OR notes LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if category in CATEGORIES:
        where.append("category = ?")
        params.append(category)

    order_by = {
        "newest": "expense_date DESC, id DESC",
        "oldest": "expense_date ASC, id ASC",
        "highest": "amount DESC, expense_date DESC",
        "lowest": "amount ASC, expense_date DESC",
    }.get(sort, "expense_date DESC, id DESC")

    sql = "SELECT id, Name AS name, amount, category, expense_date, notes FROM expense"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_by}"
    expenses = db.execute(sql, params).fetchall()

    category_rows = db.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM expense
        GROUP BY category
        ORDER BY total DESC
        """
    ).fetchall()
    category_total = sum(float(row["total"]) for row in category_rows) or 1.0
    category_breakdown = [
        {
            "category": row["category"],
            "total": float(row["total"]),
            "percent": round((float(row["total"]) / category_total) * 100, 1),
        }
        for row in category_rows[:5]
    ]

    return render_template(
        "index.html",
        expenses=expenses,
        stats=dashboard_stats(db),
        categories=CATEGORIES,
        category_breakdown=category_breakdown,
        query=query,
        selected_category=category,
        selected_sort=sort,
        today=date.today().isoformat(),
    )


@app.route("/expenses", methods=["POST"])
@app.route("/add", methods=["POST"])
def add_expense():
    try:
        name, amount, category, expense_date, notes = parse_expense_form()
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("home"))

    db = get_db()
    db.execute(
        "INSERT INTO expense (Name, amount, category, expense_date, notes) VALUES (?, ?, ?, ?, ?)",
        (name, amount, category, expense_date, notes),
    )
    db.commit()
    flash(f"Added {name}.", "success")
    return redirect(url_for("home"))


@app.route("/expenses/<int:expense_id>/update", methods=["POST"])
def update_expense(expense_id: int):
    try:
        name, amount, category, expense_date, notes = parse_expense_form()
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("home"))

    db = get_db()
    cursor = db.execute(
        """
        UPDATE expense
        SET Name = ?, amount = ?, category = ?, expense_date = ?, notes = ?
        WHERE id = ?
        """,
        (name, amount, category, expense_date, notes, expense_id),
    )
    db.commit()

    if cursor.rowcount == 0:
        flash("Expense not found.", "error")
    else:
        flash(f"Updated {name}.", "success")
    return redirect(url_for("home"))


@app.route("/expenses/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id: int):
    db = get_db()
    expense = db.execute(
        "SELECT Name AS name FROM expense WHERE id = ?", (expense_id,)
    ).fetchone()

    if expense is None:
        flash("Expense not found.", "error")
        return redirect(url_for("home"))

    db.execute("DELETE FROM expense WHERE id = ?", (expense_id,))
    db.commit()
    flash(f"Deleted {expense['name']}.", "success")
    return redirect(url_for("home"))


@app.route("/export.csv")
def export_csv():
    db = get_db()
    rows = db.execute(
        """
        SELECT expense_date, Name AS name, category, amount, notes
        FROM expense
        ORDER BY expense_date DESC, id DESC
        """
    ).fetchall()

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Date", "Expense", "Category", "Amount", "Notes"])
    for row in rows:
        writer.writerow(
            [row["expense_date"], row["name"], row["category"], f"{row['amount']:.2f}", row["notes"]]
        )

    filename = f"expenses-{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        stream.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/health")
def health():
    return {"status": "ok", "app": "expense-tracker"}


@app.template_filter("inr")
def format_inr(value: float) -> str:
    amount = float(value or 0)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    integer, decimal = f"{amount:.2f}".split(".")
    if len(integer) > 3:
        last_three = integer[-3:]
        rest = integer[:-3]
        groups = []
        while rest:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        integer = ",".join(groups + [last_three])
    return f"{sign}₹{integer}.{decimal}"


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
