"""SQLite database setup and connection management."""

import sqlite3
from pathlib import Path

# Store the database in the user's home config directory
DB_DIR = Path.home() / ".expenserule"
DB_PATH = DB_DIR / "expenses.db"
API_KEY_PATH = DB_DIR / "openai_api_key"
UPLOADS_DIR = DB_DIR / "uploads"


def ensure_dirs() -> None:
    """Create all required data directories."""
    DB_DIR.mkdir(mode=0o700, exist_ok=True)
    UPLOADS_DIR.mkdir(mode=0o700, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant        TEXT    NOT NULL,
    date            TEXT    NOT NULL,
    amount          REAL    NOT NULL,
    category        TEXT    NOT NULL,
    schedule_c_line TEXT    NOT NULL,
    notes           TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS correction_memory (
    merchant  TEXT PRIMARY KEY,
    category  TEXT NOT NULL
);
"""


def init_db() -> None:
    """Create tables if they don't already exist."""
    ensure_dirs()
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def is_first_run() -> bool:
    """Return True if no API key file exists yet."""
    return not API_KEY_PATH.exists()


def save_api_key(key: str) -> None:
    """Write the API key to disk with restricted permissions."""
    ensure_dirs()
    API_KEY_PATH.write_text(key.strip())
    API_KEY_PATH.chmod(0o600)


def load_api_key() -> str:
    """Read the stored API key."""
    return API_KEY_PATH.read_text().strip()


# ---------------------------------------------------------------------------
# Correction memory helpers
# ---------------------------------------------------------------------------


def get_correction(merchant: str) -> str | None:
    """Return the remembered category for a merchant, or None if unknown."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT category FROM correction_memory WHERE merchant = ?",
            (merchant.lower(),),
        ).fetchone()
    return row["category"] if row else None


def upsert_correction(merchant: str, category: str) -> None:
    """Store or update a merchant→category mapping in correction_memory."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO correction_memory (merchant, category) VALUES (?, ?)
            ON CONFLICT(merchant) DO UPDATE SET category = excluded.category
            """,
            (merchant.lower(), category),
        )


# ---------------------------------------------------------------------------
# Expense helpers
# ---------------------------------------------------------------------------


def save_expense(
    merchant: str,
    date: str,
    amount: float,
    category: str,
    schedule_c_line: str,
    notes: str = "",
    upload_id: str | None = None,
) -> int:
    """Insert a new expense record and return its id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO expenses (merchant, date, amount, category, schedule_c_line, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (merchant, date, amount, category, schedule_c_line, notes),
        )
        return cur.lastrowid  # type: ignore[return-value]


def update_expense_category(expense_id: int, category: str, schedule_c_line: str) -> bool:
    """Update the category on an existing expense. Returns True if a row was changed."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE expenses SET category = ?, schedule_c_line = ? WHERE id = ?",
            (category, schedule_c_line, expense_id),
        )
        return cur.rowcount > 0


def list_expenses(year: int | None = None) -> list[sqlite3.Row]:
    """Return expenses ordered newest-first, optionally filtered by year."""
    with get_connection() as conn:
        if year is not None:
            rows = conn.execute(
                "SELECT * FROM expenses WHERE strftime('%Y', date) = ? ORDER BY date DESC",
                (str(year),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM expenses ORDER BY date DESC"
            ).fetchall()
    return rows
