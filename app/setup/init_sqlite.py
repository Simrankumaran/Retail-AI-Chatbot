import os
import sqlite3
import pandas as pd

# Ensure db/ folder exists
os.makedirs("db", exist_ok=True)

conn = sqlite3.connect("db/retail.db")

# Load CSVs
products = pd.read_csv("data/products.csv")
orders = pd.read_csv("data/orders.csv")

# Write to tables
products.to_sql("products", conn, if_exists="replace", index=False)
orders.to_sql("orders", conn, if_exists="replace", index=False)

print("✅ SQLite DB created at db/retail.db")
