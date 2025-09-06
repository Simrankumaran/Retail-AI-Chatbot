import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from langchain.tools import tool
from app.utils.order_service import order_by_id, orders_by_product_name


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
        cursor = self.cursor

        @tool("OrderTrackingTool")
        def order_tracking(input: str) -> str:
            """Get order status by order ID."""
            return order_by_id(input)

        @tool("OrderTrackingByProductTool")
        def order_tracking_by_product(input: str) -> str:
            """Find up to 5 most recent orders by product name (partial match)."""
            return orders_by_product_name(input, limit=5)

        return [order_tracking, order_tracking_by_product]


# Instantiate and export tool lists
order_tools = OrderTools()
order_tool_list = order_tools.order_tool_list

# Backwards compatibility: individual references
order_tool = order_tool_list[0]
order_by_product_tool = order_tool_list[1]
