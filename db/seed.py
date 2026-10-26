import os
import random
import sqlite3
from datetime import date, timedelta

random.seed(42)  # résultats identiques à chaque exécution
DB_PATH = os.path.join(os.path.dirname(__file__), "sales.db")

REGIONS = [
    "Île-de-France", "Auvergne-Rhône-Alpes", "Occitanie",
    "Nouvelle-Aquitaine", "Bretagne", "Hauts-de-France",
]
REGION_WEIGHTS = [30, 20, 12, 14, 8, 16]  # Île-de-France vend plus

# (nom, catégorie, prix de vente, coût)
PRODUCTS = [
    ("Laptop Pro 15", "Informatique", 1200, 850),
    ("Laptop Air 13", "Informatique", 900, 640),
    ("Souris sans fil", "Informatique", 25, 10),
    ("Clavier mécanique", "Informatique", 80, 42),
    ("Écran 27 pouces", "Informatique", 320, 210),
    ("Smartphone X", "Téléphonie", 800, 560),
    ("Smartphone Lite", "Téléphonie", 300, 190),
    ("Écouteurs Bluetooth", "Audio", 120, 55),
    ("Enceinte portable", "Audio", 90, 45),
    ("Casque audio", "Audio", 200, 100),
    ("Chaise de bureau", "Mobilier", 220, 120),
    ("Bureau réglable", "Mobilier", 450, 260),
    ("Lampe LED", "Mobilier", 35, 15),
    ("Webcam HD", "Accessoires", 60, 28),
    ("Hub USB-C", "Accessoires", 45, 20),
]

FIRST_NAMES = ["Léa", "Hugo", "Emma", "Lucas", "Chloé", "Louis", "Inès",
               "Jules", "Manon", "Adam", "Sarah", "Nathan", "Camille", "Yanis"]
LAST_NAMES = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard",
              "Petit", "Durand", "Leroy", "Moreau", "Simon", "Laurent"]


def create_tables(cur):
    cur.executescript("""
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS regions;

        CREATE TABLE regions (
            region_id INTEGER PRIMARY KEY,
            region_name TEXT NOT NULL
        );

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            email TEXT,
            region_id INTEGER NOT NULL,
            segment TEXT NOT NULL,          -- 'Particulier' ou 'Entreprise'
            created_at TEXT NOT NULL,       -- format YYYY-MM-DD
            FOREIGN KEY (region_id) REFERENCES regions(region_id)
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_price REAL NOT NULL,
            unit_cost REAL NOT NULL
        );

        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY,
            sale_date TEXT NOT NULL,        -- format YYYY-MM-DD
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_amount REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)


def fill_tables(cur):
    today = date.today()

    # Régions
    for i, name in enumerate(REGIONS, start=1):
        cur.execute("INSERT INTO regions VALUES (?, ?)", (i, name))

    # Produits
    for i, (name, cat, price, cost) in enumerate(PRODUCTS, start=1):
        cur.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)",
                    (i, name, cat, price, cost))

    # Clients
    for i in range(1, 301):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        email = f"client{i}@example.com"
        region_id = random.choices(range(1, len(REGIONS) + 1), REGION_WEIGHTS)[0]
        segment = random.choices(["Particulier", "Entreprise"], [70, 30])[0]
        created = today - timedelta(days=random.randint(400, 1000))
        cur.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
                    (i, name, email, region_id, segment, created.isoformat()))

    # Ventes : 5000 sur les 2 dernières années, plus nombreuses récemment
    for i in range(1, 5001):
        days_ago = int(random.triangular(0, 730, 0))
        sale_date = today - timedelta(days=days_ago)
        customer_id = random.randint(1, 300)
        product_id = random.randint(1, len(PRODUCTS))
        quantity = random.choices([1, 2, 3, 4, 5], [50, 25, 13, 8, 4])[0]
        base_price = PRODUCTS[product_id - 1][2]
        unit_price = round(base_price * random.uniform(0.9, 1.0), 2)
        total = round(quantity * unit_price, 2)
        cur.execute("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (i, sale_date.isoformat(), customer_id, product_id,
                     quantity, unit_price, total))


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    create_tables(cur)
    fill_tables(cur)
    conn.commit()

    # Vérification
    print("Base créée :", DB_PATH)
    for table in ["regions", "customers", "products", "sales"]:
        n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n} lignes")

    print("\nChiffre d'affaires par région :")
    rows = cur.execute("""
        SELECT r.region_name, ROUND(SUM(s.total_amount), 2)
        FROM sales s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN regions r ON c.region_id = r.region_id
        GROUP BY r.region_name
        ORDER BY 2 DESC
    """).fetchall()
    for region, total in rows:
        print(f"  {region}: {total} €")

    conn.close()


if __name__ == "__main__":
    main()