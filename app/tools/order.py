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
        # Tool: order by ID
        @tool("OrderTrackingTool")
        def order_tracking(input: str) -> str:
            """Get order status by order ID."""
            return order_by_id(input)

        # Tool: order by product name
        @tool("OrderTrackingByProductTool")
        def order_tracking_by_product(input: str) -> str:
            """Find up to 5 most recent orders by product name (partial match)."""
            return orders_by_product_name(input, limit=5)

        # Tool: all orders
        @tool("AllOrdersTool")
        def all_orders_tool(limit: str = "20") -> str:
            """Get the most recent orders (default 20)."""
            return all_orders(limit=int(limit))

        # Tool: orders by status
        @tool("OrdersByStatusTool")
        def orders_by_status_tool(input: str) -> str:
            """Get recent orders filtered by status (e.g., pending, delivered)."""
            return orders_by_status(input)

        # Tool: orders by user
        @tool("OrdersByUserTool")
        def orders_by_user_tool(input: str) -> str:
            """Get recent orders placed by a given user ID."""
            return orders_by_user(input)

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
