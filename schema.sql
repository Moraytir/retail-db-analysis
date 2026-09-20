-- Retail store database (SQLite)
-- Created by build_db.py, or run it yourself in any SQLite tool.
--
-- Design notes (3NF):
--   * Each fact is stored once. Customer details live in customers, product
--     details in products, and category names in categories.
--   * order_items keeps its own unit_price so historical orders keep the price
--     that was charged at the time, even if the product price changes later.
--   * SQLite has no DATE type, so dates are stored as text in YYYY-MM-DD form,
--     which sorts and compares correctly.

PRAGMA foreign_keys = ON;

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    first_name   TEXT NOT NULL,
    last_name    TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    city         TEXT,
    signup_date  TEXT NOT NULL
);

CREATE TABLE categories (
    category_id    INTEGER PRIMARY KEY,
    category_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category_id   INTEGER NOT NULL REFERENCES categories (category_id),
    unit_price    REAL NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers (customer_id),
    order_date   TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('completed', 'cancelled'))
);

CREATE TABLE order_items (
    order_id    INTEGER NOT NULL REFERENCES orders (order_id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products (product_id),
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  REAL NOT NULL CHECK (unit_price >= 0),  -- price charged at the time of sale
    PRIMARY KEY (order_id, product_id)
);

-- Indexes for the joins and filters used in queries.sql
CREATE INDEX idx_orders_customer   ON orders (customer_id);
CREATE INDEX idx_orders_date       ON orders (order_date);
CREATE INDEX idx_items_product     ON order_items (product_id);
CREATE INDEX idx_products_category ON products (category_id);
