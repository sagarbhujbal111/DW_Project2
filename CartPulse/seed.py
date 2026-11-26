"""Deterministic, transactional Pune fixture. One fact row represents one order."""
import sqlite3
import calendar
import random
from datetime import date, timedelta
from decimal import Decimal

from database import admin_connection

ZONES = [
    ("Hinjawadi IT Park", "411057"), ("Kothrud & Karve Nagar", "411038"),
    ("Viman Nagar & Koregaon Park", "411014"), ("Pimpri-Chinchwad / PCMC", "411018"),
    ("Baner & Balewadi", "411045"), ("Hadapsar & Magarpatta", "411028"),
]
GROUPS = [
    ("Electronics & Accessories", [("Wireless earbuds","Audio",2499),("Smartphone","Mobiles",45000),("USB-C hub","Computing",1499),("Bluetooth speaker","Audio",3299)]),
    ("Home & Kitchen", [("Induction cooktop","Appliances",3499),("Steel dabba set","Storage",799),("Cast iron tawa","Cookware",1199),("Cotton bedsheet","Linen",1599)]),
    ("Apparel & Ethnic Wear", [("Paithani saree","Sarees",8499),("Cotton kurta","Kurtas",999),("Kolhapuri sandals","Footwear",1499),("Festive kurta set","Ethnic sets",2699)]),
    ("Groceries & Essentials", [("Bhajani flour pack","Pantry",299),("Chitale snack hamper","Snacks",599),("Modak gift box","Sweets",449),("Monthly staples kit","Staples",1899)]),
    ("Fitness & Lifestyle", [("Yoga mat","Yoga",899),("Sports shoes","Running",2999),("Resistance band set","Training",499),("Steel water bottle","Hydration",699)]),
]
FIRST = "Aarav Sneha Rohan Priya Siddharth Ananya Isha Om Neha Mihir Aditi Shreya Tanvi Sagar Nikhil Ishaan Kavya Aditya Meera Arya".split()
LAST = "Kulkarni Deshmukh Joshi Patil Gokhale Chitale Shah Pawar Jadhav Apte Naik More Bhide Shinde Kale".split()
SEGMENTS = ["UPI Repeat Buyer", "Prime Pune Member", "Corporate / IT Park Bulk Buyer", "New Shopper"]
YEAR = 2025


def seed(connection):
    rng = random.Random(411057)
    cursor = connection.cursor()
    def bulk(table, columns, rows):
        names = columns.split()
        if isinstance(connection, sqlite3.Connection):
            marks = ", ".join(["?"] * len(names))
            values = ([str(v) if isinstance(v, (Decimal, date)) else v for v in row] for row in rows)
            cursor.executemany(f"INSERT INTO {table} ({', '.join(names)}) VALUES ({marks})", values)
            return
        marks = ", ".join(["%s"] * len(names))
        # Explicit stable seed keys make a second load a no-op.
        cursor.executemany(f"INSERT INTO {table} ({', '.join(names)}) VALUES ({marks}) ON DUPLICATE KEY UPDATE {names[0]}={table}.{names[0]}", rows)
    try:
        bulk("dim_regions", "region_key zone_name pin_code city state country", [
            (i, *region, "Pune", "Maharashtra", "India") for i, region in enumerate(ZONES, 1)])
        prices, products = [], []
        for category, items in GROUPS:
            for name, sub, price in items:
                prices.append(price)
                products.append((len(prices), name, category, sub, round(price * rng.uniform(.48,.73), 2)))
        bulk("dim_products", "product_key product_name category sub_category unit_cost", products)
        start = date(YEAR, 1, 1)
        days = [start + timedelta(days=i) for i in range((date(YEAR+1,1,1)-start).days)]
        key = lambda d: int(d.strftime("%Y%m%d"))
        bulk("dim_date", "date_key full_date year quarter month_number month_name day_of_week", [
            (key(d), d, d.year, (d.month-1)//3+1, d.month, d.strftime("%B"), d.strftime("%A")) for d in days])
        signups, homes, customers = [], [], []
        for i in range(240):
            first, last = FIRST[i % len(FIRST)], LAST[(i//len(FIRST)+i%len(FIRST)) % len(LAST)]
            signup = start + timedelta(days=rng.randrange(340))
            signups.append(signup)
            homes.append(rng.choices(range(1,7), [25,18,17,12,16,12])[0])
            customers.append((i+1, f"{first} {last}", f"{first.lower()}.{last.lower()}@cartpulse.example.in", SEGMENTS[i%4], signup))
        bulk("dim_customers", "customer_key customer_name email segment signup_date", customers)
        orders = []
        def order(customer, day, festive):
            product = rng.choices(range(1,21), [9,1,6,5,4,6,4,4,6,8,5,6,9,7,11 if festive else 3,8,4,3,4,4])[0]
            qty = rng.choices([1,2,3,5], [72,19,7,2])[0]
            price = prices[product-1]
            discount = Decimal(rng.choice(["0","0.05","0.10","0.15"] if festive else ["0","0","0.05"]))
            orders.append((100001+len(orders), customer+1, product, homes[customer], key(day), qty, price, discount, qty*price*(1-discount)))
        for i, day in enumerate(signups):
            order(i, day, day.month in (8,9,10,11))
        for month, volume in enumerate([38,52,66,73,85,92,104,145,158,234,208,140],1):
            for _ in range(volume):
                day = date(YEAR, month, rng.randint(1, calendar.monthrange(YEAR,month)[1]))
                eligible = [i for i,d in enumerate(signups) if d <= day and i%4 != 3]
                if eligible:
                    order(rng.choice(eligible), day, month in (8,9,10,11))
        bulk("fact_orders", "order_id customer_key product_key region_key date_key quantity unit_price discount total_revenue", orders)
        connection.commit()
        return len(orders)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


if __name__ == "__main__":
    with admin_connection(database=True) as connection:
        print(f"Processed {seed(connection)} deterministic order keys.")
