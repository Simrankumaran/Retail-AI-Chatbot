from typing import List, Tuple
from .db import get_cursor


def order_by_id(order_id: str) -> str:
    cur = get_cursor()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (order_id.strip(),))
    row = cur.fetchone()
    print(row)
    return f"Order {order_id} status: {row[0]}" if row else "Order ID not found."

# Get all orders
def all_orders(limit: int = 20) -> str:
    cur = get_cursor()
    cur.execute(
        """
        SELECT o.order_id, o.user_id, o.status, o.date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        ORDER BY date(o.date) DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    if not rows:
        return "No orders found."
    return "\n".join(
        f"Order {order_id} (user {user_id}) – {status} on {date} – product: {name}"
        for (order_id, user_id, status, date, name) in rows
    )

# Orders by user ID
def orders_by_user(user_id: str, limit: int = 20) -> str:
    cur = get_cursor()
    cur.execute(
        """
        SELECT o.order_id, o.user_id, o.status, o.date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE o.user_id = ?
        ORDER BY date(o.date) DESC
        LIMIT ?
        """,
        (user_id.strip(), limit),
    )
    rows = cur.fetchall()
    if not rows:
        return f"No orders found for user {user_id}."
    return "\n".join(
        f"Order {order_id} – {status} on {date} – product: {name}"
        for (order_id, _, status, date, name) in rows
    )

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


def orders_by_status(status_filter: str, limit: int = 20) -> str:
    """Return recent orders matching a status (case-insensitive)."""
    cur = get_cursor()
    like = status_filter.strip()
    cur.execute(
        """
        SELECT o.order_id, o.user_id, o.status, o.date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE o.status = ? COLLATE NOCASE
        ORDER BY date(o.date) DESC
        LIMIT ?
        """,
        (like, limit),
    )
    rows = cur.fetchall()
    if not rows:
        return f"No orders found with status '{status_filter}'."
    return "\n".join(
        f"Order {order_id} (user {user_id}) – {status} on {date} – product: {name}"
        for (order_id, user_id, status, date, name) in rows
    )
