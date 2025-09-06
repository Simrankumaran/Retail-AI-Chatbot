from typing import List, Tuple
from .db import get_cursor


def order_by_id(order_id: str) -> str:
    cur = get_cursor()
    cur.execute(
        """
        SELECT o.status, p.name, o.date, o.user_id
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE o.order_id = ?
        """,
        (order_id.strip(),),
    )
    row = cur.fetchone()
    # Debug print for visibility in logs
    print(row)
    if not row:
        return "Order ID not found."
    status, product_name, date, user_id = row
    return f"Order {order_id} — product: {product_name} — status: {status} on {date}"

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
    """Return recent orders matching a status (case-insensitive).

    Treats common synonyms as equivalent. For example, 'pending' and
    'processing' are considered the same when filtering.
    """
    cur = get_cursor()
    key = status_filter.strip().lower()

    # Map user-friendly terms to actual status values stored in DB
    synonyms = {
        "pending": ["pending", "processing"],
        "processing": ["pending", "processing"],
        "delivered": ["delivered"],
        "cancelled": ["cancelled", "canceled"],
        "returned": ["returned"],
    }

    statuses = synonyms.get(key, [key])

    # Build SQL with an IN (...) clause for the resolved statuses
    placeholders = ",".join(["?" for _ in statuses])
    sql = f"""
        SELECT o.order_id, o.user_id, o.status, o.date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE LOWER(o.status) IN ({placeholders})
        ORDER BY date(o.date) DESC
        LIMIT ?
        """

    params = [s for s in statuses] + [limit]
    cur.execute(sql, params)
    rows = cur.fetchall()
    if not rows:
        return f"No orders found with status '{status_filter}'."
    return "\n".join(
        f"Order {order_id} (user {user_id}) – {status} on {date} – product: {name}"
        for (order_id, user_id, status, date, name) in rows
    )
