from typing import List, Tuple
from .db import get_cursor
from datetime import datetime, timezone


def order_by_id(order_id: str) -> str:
    cur = get_cursor()
    cur.execute(
        """
    SELECT o.status, p.name, o.date, o.user_id, p.id
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
    status, product_name, date, user_id, product_id = row

    # Include returnability info
    try:
        eligible, days_since, window = get_returnability_info(order_id)
    except Exception:
        eligible = False
        days_since = None
        window = None

    if eligible:
        days_left = max(0, int(window) - int(days_since)) if days_since is not None and window is not None else None
        extra = f" — RETURNABLE: Yes (days left: {days_left})" if days_left is not None else " — RETURNABLE: Yes"
    else:
        extra = f" — RETURNABLE: No (delivered {days_since} days ago; window = {window} days)" if days_since is not None and window is not None else " — RETURNABLE: No"

    return f"Order {order_id} — product: {product_name} — status: {status} on {date}{extra}"


def is_returnable(order_id: str, return_window_days: int = 7) -> bool:
    """Determine if an order is eligible for return based on delivery date.

    By default uses a 7-day window as specified in `data/return_policy.txt`.
    """
    cur = get_cursor()
    cur.execute(
        "SELECT status, date, product_id FROM orders WHERE order_id = ?",
        (order_id.strip(),),
    )
    row = cur.fetchone()
    if not row:
        return False
    status, delivered_on, product_id = row
    # Only consider delivered orders
    if status.lower() != "delivered":
        return False

    # Check product-level policy if present
    prod_policy = get_product_return_policy(product_id)
    if prod_policy is not None:
        prod_is_returnable, prod_window = prod_policy
        if prod_is_returnable is False:
            return False
        # prefer product-level window if provided
        if prod_window is not None:
            return_window_days = prod_window

    try:
        # Accept ISO-like or common YYYY-MM-DD formats
        delivered_date = datetime.fromisoformat(delivered_on)
    except Exception:
        try:
            delivered_date = datetime.strptime(delivered_on, "%Y-%m-%d")
        except Exception:
            # If parsing fails, conservatively return False
            return False

    # Normalize timezone: if delivered_date is naive, assume UTC for comparisons.
    if delivered_date.tzinfo is None:
        delivered_date = delivered_date.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    delta = now - delivered_date
    return delta.days <= int(return_window_days)


def get_returnability_info(order_id: str, default_window: int = 7):
    """Return tuple (eligible: bool, days_since: int, window: int).

    Raises on parse errors.
    """
    cur = get_cursor()
    cur.execute("SELECT status, date, product_id FROM orders WHERE order_id = ?", (order_id.strip(),))
    row = cur.fetchone()
    if not row:
        raise ValueError("order not found")
    status, delivered_on, product_id = row
    if status.lower() != "delivered":
        return (False, None, None)

    prod_policy = get_product_return_policy(product_id)
    prod_is_returnable = True
    prod_window = default_window
    if prod_policy is not None:
        prod_is_returnable, prod_window = prod_policy
        if prod_window is None:
            prod_window = default_window

    if prod_is_returnable is False:
        return (False, None, prod_window)

    try:
        delivered_date = datetime.fromisoformat(delivered_on)
    except Exception:
        delivered_date = datetime.strptime(delivered_on, "%Y-%m-%d")

    if delivered_date.tzinfo is None:
        delivered_date = delivered_date.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    days_since = (now - delivered_date).days
    eligible = days_since <= int(prod_window)
    return (eligible, days_since, int(prod_window))


def get_product_return_policy(product_id: int):
    """Return (is_returnable: bool or None, return_window_days: int or None).

    If the products table doesn't have policy columns, attempt to add them with safe defaults.
    Returns None if product not found.
    """
    conn_cur = get_cursor()
    # Ensure policy columns exist; ALTER TABLE is idempotent for adding columns
    try:
        conn = conn_cur.connection
    except Exception:
        conn = None

    # Check columns
    cur = get_cursor()
    cur.execute("PRAGMA table_info(products)")
    cols = [r[1] for r in cur.fetchall()]
    if "is_returnable" not in cols:
        try:
            cur.execute("ALTER TABLE products ADD COLUMN is_returnable INTEGER DEFAULT 1")
            if conn:
                conn.commit()
        except Exception:
            pass
    if "return_window_days" not in cols:
        try:
            cur.execute("ALTER TABLE products ADD COLUMN return_window_days INTEGER DEFAULT 7")
            if conn:
                conn.commit()
        except Exception:
            pass

    cur.execute("SELECT is_returnable, return_window_days FROM products WHERE id = ?", (product_id,))
    prow = cur.fetchone()
    if not prow:
        return None
    is_ret, win = prow
    is_ret_bool = None if is_ret is None else bool(is_ret)
    return (is_ret_bool, None if win is None else int(win))

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


def orders_returnable_by_user(user_id: str, return_window_days: int = 7, limit: int = 100) -> str:
    """Return a list of this user's orders that are eligible for return.

    Scans recent orders for the user and uses `is_returnable` to filter.
    Returns a human-readable multi-line string; empty -> message explaining none found.
    """
    cur = get_cursor()
    cur.execute(
        """
        SELECT o.order_id, o.status, o.date, p.name
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

    result_lines = []
    for order_id, status, date, product_name in rows:
        # Only check returnability for delivered orders to keep it fast
        if status and status.lower() == "delivered":
            try:
                if is_returnable(order_id, return_window_days=return_window_days):
                    result_lines.append(f"Order {order_id} — product: {product_name} — delivered on {date} — RETURNABLE")
            except Exception:
                # On parse/parity errors, skip conservatively
                continue

    if not result_lines:
        return f"No returnable orders found for user {user_id} within the last {return_window_days} days."

    return "\n".join(result_lines)
