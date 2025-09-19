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
    can_cancel_order,
    cancel_order,
    get_cancellable_orders,
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
                order = order_by_id(order_id)
                if not order or not order.get("found", False):
                    return {"found": False, "order_id": order_id, "error": "Order not found"}
                # Return the order data directly instead of nesting it
                return order
            except Exception as e:
                return {"found": False, "error": str(e), "order_id": order_id}

        @tool("OrderTrackingByProductTool")
        def order_tracking_by_product(product_name: str) -> dict:
            """Find up to 5 most recent orders by product name (partial match)."""
            try:
                # Return the service result directly (it already has proper found/orders structure)
                return orders_by_product_name(product_name, limit=5)
            except Exception as e:
                return {"found": False, "error": str(e), "product_name": product_name, "orders": []}

        @tool("AllOrdersTool")
        def all_orders_tool(limit: int = 20) -> dict:
            """Get the most recent orders, default limit is 20."""
            try:
                # Return the service result directly
                return all_orders(limit)
            except Exception as e:
                return {"found": False, "error": str(e), "limit": limit, "orders": []}

        @tool("OrdersByStatusTool")
        def orders_by_status_tool(status: str) -> dict:
            """Get recent orders filtered by status (pending, shipped, delivered, cancelled)."""
            try:
                # Return the service result directly
                return orders_by_status(status)
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
                # Return the service result directly
                return orders_by_user(user_id)
            except Exception as e:
                return {"found": False, "error": str(e), "user_id": user_id, "orders": []}

        @tool("OrderCancellationCheckTool")
        def check_order_cancellation(order_id: str) -> dict:
            """Check if an order can be cancelled (only 'processing' orders allowed)."""
            try:
                return can_cancel_order(order_id)
            except Exception as e:
                return {"can_cancel": False, "error": str(e), "order_id": order_id}

        @tool("OrderCancellationTool")
        def cancel_order_tool(order_id: str, reason: str = "Customer request") -> dict:
            """Cancel an order by order ID (only 'processing' orders allowed). Provide a reason for cancellation."""
            try:
                return cancel_order(order_id, reason)
            except Exception as e:
                return {"success": False, "error": str(e), "order_id": order_id}

        @tool("CancellableOrdersTool")
        def get_cancellable_orders_tool(user_id: str = "2001") -> dict:
            """Get all orders that can be cancelled for user 2001 (only 'processing' orders). Use user_id parameter to override default."""
            try:
                return get_cancellable_orders(user_id, limit=20)
            except Exception as e:
                return {"found": False, "error": str(e), "cancellable_orders": []}

        @tool("MyOrdersTool")
        def my_orders_tool(limit: int = 20) -> dict:
            """Get recent orders for the current user (user 2001). This is for queries like 'my orders', 'show my recent orders'."""
            try:
                return orders_by_user("2001", limit)
            except Exception as e:
                return {"found": False, "error": str(e), "user_id": "2001", "orders": []}

        return [
            order_tracking,
            order_tracking_by_product,
            all_orders_tool,
            orders_by_status_tool,
            orders_by_user_tool,
            check_order_cancellation,
            cancel_order_tool,
            get_cancellable_orders_tool,
            my_orders_tool,
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
order_cancellation_check_tool = order_tool_list[5]
order_cancellation_tool = order_tool_list[6]
cancellable_orders_tool = order_tool_list[7]
my_orders_tool = order_tool_list[8]
