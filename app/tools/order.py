import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from langchain.tools import tool
from app.utils.order_service import (
    order_by_id,
    orders_by_product_name,
    all_orders,
    orders_by_status,
    orders_by_user,
)


class OrderTools:
    def __init__(self):
        load_dotenv()
        base_dir = Path(__file__).resolve().parent.parent.parent
        db_rel = os.getenv("DB_PATH", "db/retail.db")
        db_path = (base_dir / db_rel).resolve()
        if not db_path.exists():
            raise FileNotFoundError(f"DB file not found at: {db_path}")

        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.order_tool_list = self._setup_tools()

    def _setup_tools(self):
        @tool("OrderTrackingTool")
        def order_tracking(order_id: str) -> dict:
            """Retrieve the status and details of an order by its order ID."""
            try:
                order = order_by_id(order_id, include_return_info=True)
                if not order or "Order ID not found" in order:
                    return {"found": False, "order_id": order_id}
                return {"found": True, "order_id": order_id, "details": order}
            except Exception as e:
                return {"found": False, "error": str(e), "order_id": order_id}

        @tool("OrderTrackingByProductTool")
        def order_tracking_by_product(product_name: str) -> dict:
            """Find up to 5 most recent orders by product name (partial match)."""
            try:
                orders = orders_by_product_name(product_name, limit=5)
                # Ensure orders is always a list
                orders_list = orders if isinstance(orders, list) else [orders] if orders else []
                return {"found": bool(orders_list), "product_name": product_name, "orders": orders_list}
            except Exception as e:
                return {"found": False, "error": str(e), "product_name": product_name, "orders": []}

        @tool("AllOrdersTool")
        def all_orders_tool(limit: int = 20) -> dict:
            """Get the most recent orders, default limit is 20."""
            try:
                orders = all_orders(limit)
                orders_list = orders if isinstance(orders, list) else [orders] if orders else []
                return {"found": bool(orders_list), "limit": limit, "orders": orders_list}
            except Exception as e:
                return {"found": False, "error": str(e), "limit": limit, "orders": []}

        @tool("OrdersByStatusTool")
        def orders_by_status_tool(status: str) -> dict:
            """Get recent orders filtered by status (pending, shipped, delivered, cancelled)."""
            try:
                orders = orders_by_status(status)
                orders_list = orders if isinstance(orders, list) else [orders] if orders else []
                return {"found": bool(orders_list), "status": status, "orders": orders_list}
            except Exception as e:
                import traceback
                return {
                    "found": False,
                    "status": status,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "orders": [],
                }

        @tool("OrdersByUserTool")
        def orders_by_user_tool(user_id: str) -> dict:
            """Get recent orders placed by a given user ID."""
            try:
                orders = orders_by_user(user_id)
                orders_list = orders if isinstance(orders, list) else [orders] if orders else []
                return {"found": bool(orders_list), "user_id": user_id, "orders": orders_list}
            except Exception as e:
                return {"found": False, "error": str(e), "user_id": user_id, "orders": []}

        return [
            order_tracking,
            order_tracking_by_product,
            all_orders_tool,
            orders_by_status_tool,
            orders_by_user_tool,
        ]


# Instantiate and export tool lists
order_tools = OrderTools()
order_tool_list = order_tools.order_tool_list

# Backwards compatibility: individual references
order_tool = order_tool_list[0]
order_by_product_tool = order_tool_list[1]
all_orders_tool = order_tool_list[2]
orders_by_status_tool = order_tool_list[3]
orders_by_user_tool = order_tool_list[4]
