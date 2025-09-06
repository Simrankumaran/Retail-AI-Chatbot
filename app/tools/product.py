import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from langchain.tools import tool
from app.utils.product_service import search_products as svc_search_products, products_in_category as svc_products_in_category, price_of_product as svc_price_of_product

# Pattern aligned with PlaceSearchTool: class + @tool functions + tool list

class ProductTools:
    def __init__(self):
        load_dotenv()
        base_dir = Path(__file__).resolve().parent.parent.parent
        db_rel = os.getenv("DB_PATH", "db/retail.db")
        db_path = (base_dir / db_rel).resolve()
        if not db_path.exists():
            raise FileNotFoundError(f"DB file not found at: {db_path}")
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.product_tool_list = self._setup_tools()

    def _setup_tools(self):
        cursor = self.cursor

        @tool("ProductSearchTool")
        def product_search(input: str) -> str:
            """Find product names and prices by partial name or category; supports 'under/over' and 'between' price filters."""
            rows = svc_search_products(input)
            if not rows:
                return "No matching products found."
            return "\n".join(f"{name} – ₹{price}" for name, price in rows)

        @tool("ProductCategoryTool")
        def products_in_category(input: str) -> str:
            """List products in a given category."""
            rows = svc_products_in_category(input)
            if not rows:
                return "No products found in that category."
            return "\n".join(f"{name} – ₹{price}" for name, price in rows)

        @tool("ProductPriceTool")
        def price_of_product(input: str) -> str:
            """Get the price for a product by name (partial match)."""
            rows = svc_price_of_product(input)
            if not rows:
                return "No products found with that name."
            return "\n".join(f"{n} – ₹{p}" for n, p in rows)

        return [product_search, products_in_category, price_of_product]


# Instantiate and export tool list
product_tools = ProductTools()
product_tool_list = product_tools.product_tool_list

# Backwards compatibility: primary search tool reference
product_tool = product_tool_list[0]
