"""
Generate SYNTHETIC retail data for the database in schema.sql.

Every value here is made up for demonstration. Nothing comes from a real store
or real customers. The random seed is fixed, so you always get the same data.

Usage:
    python generate_data.py

Creates CSV files in data/ (categories, products, customers, orders, order_items).
build_db.py calls this for you, so you normally do not need to run it yourself.
"""

import csv
import datetime as dt
import random
from pathlib import Path

SEED = 42
N_CUSTOMERS = 300
DATA_START = dt.date(2025, 1, 1)
DATA_END = dt.date(2025, 12, 31)
CANCEL_RATE = 0.04
OUT_DIR = Path("data")

random.seed(SEED)

# (product name, category, unit price in THB)
PRODUCTS = [
    ("Bottled Water 1.5L", "Beverages", 12),
    ("Iced Tea", "Beverages", 20),
    ("Cola", "Beverages", 15),
    ("Orange Juice", "Beverages", 35),
    ("Instant Coffee 3-in-1 (10 sachets)", "Beverages", 65),
    ("Green Tea Bottle", "Beverages", 18),
    ("Potato Chips", "Snacks", 25),
    ("Seaweed Snack", "Snacks", 20),
    ("Chocolate Bar", "Snacks", 30),
    ("Biscuit Pack", "Snacks", 22),
    ("Roasted Peanuts", "Snacks", 28),
    ("Instant Noodle Cup", "Snacks", 15),
    ("Jasmine Rice 5kg", "Groceries", 185),
    ("Cooking Oil 1L", "Groceries", 55),
    ("Eggs (10)", "Groceries", 60),
    ("Fish Sauce", "Groceries", 40),
    ("Soy Sauce", "Groceries", 35),
    ("Sugar 1kg", "Groceries", 28),
    ("Dish Soap", "Household", 45),
    ("Laundry Detergent", "Household", 120),
    ("Tissue Roll 6-pack", "Household", 75),
    ("Trash Bags", "Household", 35),
    ("Sponge 3-pack", "Household", 30),
    ("Shampoo", "Personal Care", 89),
    ("Toothpaste", "Personal Care", 55),
    ("Body Wash", "Personal Care", 95),
    ("Hand Soap", "Personal Care", 49),
    ("Toothbrush 2-pack", "Personal Care", 39),
]

# When a basket has one category, the next item often comes from a related one.
COMPANION = {
    "Beverages": "Snacks",
    "Snacks": "Beverages",
    "Groceries": "Groceries",
    "Household": "Personal Care",
    "Personal Care": "Household",
}

FIRST_NAMES = ["Somchai", "Malee", "Anan", "Napat", "Pim", "Krit", "Ploy", "Tanawat", "Suda", "Wichai",
               "Mali", "Chai", "Nida", "Arun", "Kanya", "Piti", "Rattana", "Sarawut", "Lalita", "Thira"]
LAST_NAMES = ["Srisuk", "Chaiyo", "Boonmee", "Wongsawat", "Kaewmanee", "Thongdee", "Saetang", "Rattanakul",
              "Jaidee", "Phromma", "Sukjai", "Meesuk", "Charoen", "Pattana", "Intarasak"]
CITIES = ["Bangkok", "Nonthaburi", "Samut Prakan", "Pathum Thani", "Chiang Mai", "Khon Kaen"]
CITY_WEIGHTS = [50, 15, 10, 10, 8, 7]


def write_csv(name, header, rows):
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {name}: {len(rows):,} rows")


def random_date(start, end):
    return start + dt.timedelta(days=random.randint(0, (end - start).days))


def pick_product(products_by_cat, weights, exclude, category=None):
    """Pick a product, optionally from one category, that is not already in the basket."""
    pool = [p for p in weights if p not in exclude and (category is None or products_by_cat[p] == category)]
    if not pool:
        pool = [p for p in weights if p not in exclude]
    return random.choices(pool, weights=[weights[p] for p in pool])[0]


def main():
    # categories and products
    categories = sorted({c for _, c, _ in PRODUCTS}, key=[c for _, c, _ in PRODUCTS].index)
    cat_id = {name: i for i, name in enumerate(categories, start=1)}
    write_csv("categories.csv", ["category_id", "category_name"], [(i, n) for n, i in cat_id.items()])

    product_rows = [(i, name, cat_id[cat], price) for i, (name, cat, price) in enumerate(PRODUCTS, start=1)]
    write_csv("products.csv", ["product_id", "product_name", "category_id", "unit_price"], product_rows)
    price_of = {row[0]: row[3] for row in product_rows}
    category_of = {row[0]: PRODUCTS[row[0] - 1][1] for row in product_rows}
    # popularity: cheaper items are bought more often
    weights = {pid: 1.0 + 60.0 / (price_of[pid] + 10) for pid in price_of}

    # customers
    customer_rows = []
    signup = {}
    for cid in range(1, N_CUSTOMERS + 1):
        first, last = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        signup[cid] = random_date(dt.date(2024, 7, 1), dt.date(2025, 11, 30))
        customer_rows.append(
            (cid, first, last, f"{first.lower()}.{last.lower()}{cid}@example.com",
             random.choices(CITIES, weights=CITY_WEIGHTS)[0], signup[cid])
        )
    write_csv("customers.csv", ["customer_id", "first_name", "last_name", "email", "city", "signup_date"], customer_rows)

    # orders and order items
    order_rows, item_rows = [], []
    order_id = 0
    for cid in range(1, N_CUSTOMERS + 1):
        window_start = max(signup[cid], DATA_START)
        # some customers stop buying before the end of the year (lapsed)
        window_end = DATA_END if random.random() < 0.6 else random_date(window_start, DATA_END)
        window_days = max((window_end - window_start).days, 1)
        n_orders = max(1, min(int(random.expovariate(1 / 7)) + 1, window_days // 5))
        dates = sorted(random_date(window_start, window_end) for _ in range(n_orders))

        for order_date in dates:
            order_id += 1
            status = "cancelled" if random.random() < CANCEL_RATE else "completed"
            order_rows.append((order_id, cid, order_date, status))

            basket_size = random.choices([1, 2, 3, 4, 5], weights=[30, 30, 20, 12, 8])[0]
            basket = []
            first = pick_product(category_of, weights, basket)
            basket.append(first)
            while len(basket) < basket_size:
                if random.random() < 0.5:
                    nxt = pick_product(category_of, weights, basket, COMPANION[category_of[first]])
                else:
                    nxt = pick_product(category_of, weights, basket)
                basket.append(nxt)
            for pid in basket:
                qty = random.choices([1, 2, 3], weights=[70, 22, 8])[0]
                item_rows.append((order_id, pid, qty, price_of[pid]))

    write_csv("orders.csv", ["order_id", "customer_id", "order_date", "status"], order_rows)
    write_csv("order_items.csv", ["order_id", "product_id", "quantity", "unit_price"], item_rows)
    print(f"\nSaved to {OUT_DIR}/. Next: python build_db.py")


if __name__ == "__main__":
    main()
