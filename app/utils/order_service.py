from typing import List, Dict, Optional
from .db import get_cursor
from datetime import datetime, timezone

# ---------- Helper functions ----------

def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string and normalize to UTC."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def get_product_return_policy(product_id: int, default_window: int = 7) -> Dict:
    """Return product-level return policy."""
    cur = get_cursor()
    cur.execute("PRAGMA table_info(products)")
    cols = [r[1] for r in cur.fetchall()]
    conn = cur.connection

    # Add missing columns if necessary
    if "is_returnable" not in cols:
        try:
            cur.execute("ALTER TABLE products ADD COLUMN is_returnable INTEGER DEFAULT 1")
            conn.commit()
        except Exception:
            pass
    if "return_window_days" not in cols:
        try:
            cur.execute("ALTER TABLE products ADD COLUMN return_window_days INTEGER DEFAULT 7")
            conn.commit()
        except Exception:
            pass

    cur.execute(
        "SELECT is_returnable, return_window_days FROM products WHERE id = ?", (product_id,)
    )
    row = cur.fetchone()
    if not row:
        return {"is_returnable": None, "return_window_days": default_window}
    is_ret, win = row
    return {
        "is_returnable": None if is_ret is None else bool(is_ret),
        "return_window_days": None if win is None else int(win),
    }

def is_returnable(order_id: str, return_window_days: int = 7) -> bool:
    cur = get_cursor()
    cur.execute("SELECT status, delivered_date, product_id FROM orders WHERE order_id = ?", (order_id.strip(),))
    row = cur.fetchone()
    if not row:
        return False
    status, delivered_on, product_id = row
    if status.lower() != "delivered":
        return False
    policy = get_product_return_policy(product_id)
    window = policy.get("return_window_days", return_window_days)
    dt = parse_date(delivered_on)
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    return (now - dt).days <= window

def get_returnability_info(order_id: str, default_window: int = 7) -> Dict:
    """Return structured return eligibility info."""
    cur = get_cursor()
    cur.execute("SELECT status, delivered_date, product_id FROM orders WHERE order_id = ?", (order_id.strip(),))
    row = cur.fetchone()
    if not row:
        return {"eligible": False, "days_since": None, "window": None}
    status, delivered_on, product_id = row
    if status.lower() != "delivered":
        return {"eligible": False, "days_since": None, "window": None}

    policy = get_product_return_policy(product_id, default_window)
    window = policy.get("return_window_days", default_window)
    dt = parse_date(delivered_on)
    if not dt:
        return {"eligible": False, "days_since": None, "window": window}

    now = datetime.now(timezone.utc)
    days_since = (now - dt).days
    eligible = days_since <= window
    return {"eligible": eligible, "days_since": days_since, "window": window}

# ---------- Order queries ----------

def order_by_id(order_id: str) -> Dict:
    cur = get_cursor()
    cur.execute(
        """
        SELECT o.status, p.name, o.delivered_date, o.user_id, p.id
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE o.order_id = ?
        """,
        (order_id.strip(),)
    )
    row = cur.fetchone()
    if not row:
        return {"found": False, "order_id": order_id}

    status, product_name, date, user_id, product_id = row
    returnability = get_returnability_info(order_id)
    return {
        "found": True,
        "order_id": order_id,
        "product_name": product_name,
        "status": status,
        "date": date,
        "user_id": user_id,
        "returnable": returnability.get("eligible"),
        "days_since_delivery": returnability.get("days_since"),
        "return_window_days": returnability.get("window")
    }

def orders_by_product_name(product_name: str, limit: int = 5) -> Dict:
    cur = get_cursor()
    like = f"%{product_name.strip()}%"
    cur.execute(
        """
        SELECT o.order_id, o.user_id, o.status, o.ordered_date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE p.name LIKE ? COLLATE NOCASE
        ORDER BY date(o.ordered_date) DESC
        LIMIT ?
        """,
        (like, limit)
    )
    rows = cur.fetchall()
    if not rows:
        return {"found": False, "query": product_name, "orders": []}

    orders = [
        {"order_id": oid, "user_id": uid, "status": st, "date": dt, "product_name": pname}
        for oid, uid, st, dt, pname in rows
    ]
    return {"found": True, "query": product_name, "orders": orders}

def all_orders(limit: int = 20) -> Dict:
    cur = get_cursor()
    cur.execute(
        """
        SELECT o.order_id, o.user_id, o.status, o.ordered_date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        ORDER BY date(o.ordered_date) DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = cur.fetchall()
    orders = [
        {"order_id": oid, "user_id": uid, "status": st, "date": dt, "product_name": pname}
        for oid, uid, st, dt, pname in rows
    ]
    return {"found": bool(rows), "orders": orders}

def orders_by_user(user_id: str, limit: int = 20) -> Dict:
    cur = get_cursor()
    cur.execute(
        """
        SELECT o.order_id, o.user_id, o.status, o.ordered_date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE o.user_id = ?
        ORDER BY date(o.ordered_date) DESC
        LIMIT ?
        """,
        (user_id.strip(), limit)
    )
    rows = cur.fetchall()
    orders = [
        {"order_id": oid, "user_id": uid, "status": st, "date": dt, "product_name": pname}
        for oid, uid, st, dt, pname in rows
    ]
    return {"found": bool(rows), "user_id": user_id, "orders": orders}

def orders_by_status(status_filter: str, limit: int = 20) -> Dict:
    cur = get_cursor()
    key = status_filter.strip().lower()
    synonyms = {
        "pending": ["pending", "processing"],
        "processing": ["pending", "processing"],
        "delivered": ["delivered"],
        "cancelled": ["cancelled", "canceled"],
        "returned": ["returned"],
    }
    statuses = synonyms.get(key, [key])
    placeholders = ",".join(["?" for _ in statuses])
    sql = f"""
        SELECT o.order_id, o.user_id, o.status, o.ordered_date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE LOWER(o.status) IN ({placeholders})
        ORDER BY date(o.ordered_date) DESC
        LIMIT ?
    """
    cur.execute(sql, [s for s in statuses] + [limit])
    rows = cur.fetchall()
    orders = [
        {"order_id": oid, "user_id": uid, "status": st, "date": dt, "product_name": pname}
        for oid, uid, st, dt, pname in rows
    ]
    return {"found": bool(rows), "status_filter": status_filter, "orders": orders}

def orders_returnable_by_user(user_id: str, return_window_days: int = 7, limit: int = 100) -> Dict:
    cur = get_cursor()
    cur.execute(
        """
        SELECT o.order_id, o.status, o.delivered_date, p.name
        FROM orders o
        JOIN products p ON p.id = o.product_id
        WHERE o.user_id = ?
        ORDER BY date(o.delivered_date) DESC
        LIMIT ?
        """,
        (user_id.strip(), limit)
    )
    rows = cur.fetchall()
    returnable_orders = []
    for order_id, status, date, product_name in rows:
        if status.lower() == "delivered" and is_returnable(order_id, return_window_days):
            returnable_orders.append({
                "order_id": order_id,
                "product_name": product_name,
                "date": date,
                "user_id": user_id,
                "returnable": True
            })
    return {
        "found": bool(returnable_orders),
        "user_id": user_id,
        "orders": returnable_orders
    }

# ---------- Order cancellation functions ----------

def can_cancel_order(order_id: str) -> Dict:
    """Check if an order can be cancelled based on its current status (only processing orders allowed)."""
    cur = get_cursor()
    cur.execute("SELECT status, ordered_date FROM orders WHERE order_id = ?", (order_id.strip(),))
    row = cur.fetchone()
    
    if not row:
        return {"can_cancel": False, "reason": "Order not found", "order_id": order_id}
    
    status, ordered_date = row
    status_lower = status.lower()
    
    # Define cancellation rules - only processing orders can be cancelled
    if status_lower == "processing":
        return {"can_cancel": True, "reason": "Order can be cancelled", "order_id": order_id, "status": status}
    elif status_lower == "delivered":
        return {"can_cancel": False, "reason": "Delivered orders cannot be cancelled", "order_id": order_id, "status": status}
    elif status_lower in ["cancelled", "canceled"]:
        return {"can_cancel": False, "reason": "Order already cancelled", "order_id": order_id, "status": status}
    elif status_lower in ["pending", "shipped"]:
        return {"can_cancel": False, "reason": f"Orders with status '{status}' cannot be cancelled", "order_id": order_id, "status": status}
    else:
        return {"can_cancel": False, "reason": f"Cannot cancel order with status: {status}", "order_id": order_id, "status": status}

def cancel_order(order_id: str, reason: str = "Customer request") -> Dict:
    """Cancel an order by updating its status to cancelled."""
    cur = get_cursor()
    conn = cur.connection
    
    # First check if cancellation is allowed
    can_cancel = can_cancel_order(order_id)
    if not can_cancel.get("can_cancel", False):
        return {
            "success": False, 
            "order_id": order_id,
            "error": can_cancel.get("reason", "Cancellation not allowed"),
            "current_status": can_cancel.get("status")
        }
    
    try:
        # Get current order details for logging
        cur.execute(
            "SELECT o.status, p.name FROM orders o JOIN products p ON o.product_id = p.id WHERE o.order_id = ?", 
            (order_id.strip(),)
        )
        order_details = cur.fetchone()
        
        if not order_details:
            return {"success": False, "order_id": order_id, "error": "Order not found"}
        
        current_status, product_name = order_details
        
        # Update order status to cancelled
        cur.execute(
            "UPDATE orders SET status = 'cancelled' WHERE order_id = ?", 
            (order_id.strip(),)
        )
        
        if cur.rowcount == 0:
            return {"success": False, "order_id": order_id, "error": "Failed to update order status"}
        
        conn.commit()
        
        return {
            "success": True,
            "order_id": order_id,
            "product_name": product_name,
            "previous_status": current_status,
            "new_status": "cancelled",
            "cancellation_reason": reason,
            "message": f"Order {order_id} for {product_name} has been successfully cancelled"
        }
        
    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "order_id": order_id,
            "error": f"Database error: {str(e)}"
        }

def get_cancellable_orders(user_id: str = None, limit: int = 20) -> Dict:
    """Get orders that can be cancelled (processing status only)."""
    cur = get_cursor()
    
    # Build query based on whether user_id is provided - only processing orders
    if user_id:
        sql = """
            SELECT o.order_id, o.user_id, o.status, o.ordered_date, p.name
            FROM orders o
            JOIN products p ON p.id = o.product_id
            WHERE o.user_id = ? AND LOWER(o.status) = 'processing'
            ORDER BY date(o.ordered_date) DESC
            LIMIT ?
        """
        params = (user_id.strip(), limit)
    else:
        sql = """
            SELECT o.order_id, o.user_id, o.status, o.ordered_date, p.name
            FROM orders o
            JOIN products p ON p.id = o.product_id
            WHERE LOWER(o.status) = 'processing'
            ORDER BY date(o.ordered_date) DESC
            LIMIT ?
        """
        params = (limit,)
    
    cur.execute(sql, params)
    rows = cur.fetchall()
    
    # All processing orders are cancellable
    cancellable_orders = []
    now = datetime.now(timezone.utc)
    
    for oid, uid, st, dt, pname in rows:
        order_dt = parse_date(dt)
        days_since_order = (now - order_dt).days if order_dt else None
        
        cancellable_orders.append({
            "order_id": oid, 
            "user_id": uid, 
            "status": st, 
            "date": dt, 
            "product_name": pname,
            "can_cancel": True,
            "days_since_order": days_since_order
        })
    
    return {
        "found": bool(cancellable_orders),
        "user_id": user_id,
        "cancellable_orders": cancellable_orders,
        "count": len(cancellable_orders)
    }
