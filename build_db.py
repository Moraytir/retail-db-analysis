"""
Build the SQLite database (retail.db) from schema.sql and the generated CSV files.

Usage:
    python build_db.py

If data/ does not exist yet, it is created first with generate_data.py
(synthetic data, fixed random seed). Running this again rebuilds retail.db.
"""

import csv
import sqlite3
from pathlib import Path

import generate_data

DB_PATH = Path("retail.db")
DATA_DIR = Path("data")
SCHEMA_FILE = Path("schema.sql")

# Load parents before children so foreign keys are satisfied.
TABLES = [
    ("categories", ["category_id", "category_name"]),
    ("products", ["product_id", "product_name", "category_id", "unit_price"]),
    ("customers", ["customer_id", "first_name", "last_name", "email", "city", "signup_date"]),
    ("orders", ["order_id", "customer_id", "order_date", "status"]),
    ("order_items", ["order_id", "product_id", "quantity", "unit_price"]),
]


def main():
    if not (DATA_DIR / "orders.csv").exists():
        print("Generating synthetic data...")
        generate_data.main()

    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))

    for table, columns in TABLES:
        with open(DATA_DIR / f"{table}.csv", newline="", encoding="utf-8") as f:
            rows = [tuple(row[c] for c in columns) for row in csv.DictReader(f)]
        placeholders = ", ".join("?" * len(columns))
        conn.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows)
    conn.commit()

    print(f"\nBuilt {DB_PATH}:")
    for table, _ in TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,} rows")
    conn.close()
    print("\nNext: python analysis.py")


if __name__ == "__main__":
    main()
