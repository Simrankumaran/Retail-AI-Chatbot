from typing import List, Tuple
from .db import get_cursor


def order_by_id(order_id: str) -> str:
    cur = get_cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (order_id.strip(),))
    row = cur.fetchone()
    print(row)
    return f"Order {order_id} status: {row[0]}" if row else "Order ID not found."

# add all orders sql

def orders_by_product_name(product_name: str, limit: int = 5) -> str:
    cur = get_cursor()
    like = f"%{product_name.strip()}%"
    cur.execute(
        """
        SELECT o.order_id, o.user_id, o.status, o.date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE p.name LIKE ? COLLATE NOCASE
        ORDER BY date(o.date) DESC
        LIMIT ?
        """,
        (like, limit),
    )
    rows = cur.fetchall()
    if not rows:
        return "No orders found for a product matching that name."
    return "\n".join(
        f"Order {order_id} (user {user_id}) – {status} on {date} – product: {name}"
        for (order_id, user_id, status, date, name) in rows
    )
