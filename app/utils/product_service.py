from typing import List, Tuple
import re
from .db import get_cursor


def _to_number(num_str: str, has_k: str | None) -> float:
    val = float(num_str)
    return val * 1000 if has_k else val


def parse_price_filter(text: str) -> Tuple[str | None, float | None, float | None]:
    """Parse price filters like:
    - under/below/less than 60k
    - over/above/more than 30000
    - between 30k and 50k / from 30k to 50k / 30000 to 50000
    Returns (op, v1, v2) where op in {'<','>','between', None}.
    """
    t = text.lower().replace(",", "").replace("₹", "")

    # Range patterns
    m_range = re.search(r"\b(?:between|from)?\s*(\d+(?:\.\d+)?)\s*(k)?\s*(?:to|and|-)\s*(\d+(?:\.\d+)?)\s*(k)?\b", t)
    if m_range:
        v1 = _to_number(m_range.group(1), m_range.group(2))
        v2 = _to_number(m_range.group(3), m_range.group(4))
        lo, hi = (v1, v2) if v1 <= v2 else (v2, v1)
        return ("between", lo, hi)

    m_under = re.search(r"\b(under|below|less than)\s*(\d+(?:\.\d+)?)\s*(k)?\b", t)
    if m_under:
        val = _to_number(m_under.group(2), m_under.group(3))
        return ("<", val, None)

    m_over = re.search(r"\b(over|above|more than)\s*(\d+(?:\.\d+)?)\s*(k)?\b", t)
    if m_over:
        val = _to_number(m_over.group(2), m_over.group(3))
        return (">", val, None)

    return (None, None, None)


def extract_terms(text: str) -> List[str]:
    t = text.lower()
    t = re.sub(r"[₹,]", " ", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    stop = {
        "show", "find", "list", "give", "me", "under", "below", "less", "than",
        "over", "above", "more", "between", "and", "to", "from", "price", "priced",
        "products", "items", "the", "of", "for", "with", "in",
    }
    tokens = [w for w in t.split() if not w.isdigit() and w not in stop]
    # naive singularization
    normalized = [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in tokens]
    return normalized


def search_products(query: str) -> List[tuple]:
    """Search products by tokens in name/category and optional price filter (under/over/between)."""
    cur = get_cursor()
    op, v1, v2 = parse_price_filter(query)
    terms = extract_terms(query)

    where = []
    params: list = []

    if terms:
        name_or_cat = []
        for w in terms:
            name_or_cat.append("(name LIKE ? OR category LIKE ?)")
            like = f"%{w}%"
            params.extend([like, like])
        where.append("(" + " OR ".join(name_or_cat) + ")")

    if op == "<" and v1 is not None:
        where.append("price < ?")
        params.append(v1)
    elif op == ">" and v1 is not None:
        where.append("price > ?")
        params.append(v1)
    elif op == "between" and v1 is not None and v2 is not None:
        where.append("price BETWEEN ? AND ?")
        params.extend([v1, v2])

    where_sql = " AND ".join(where) if where else "1=1"
    sql = f"SELECT name, price FROM products WHERE {where_sql} LIMIT 50"
    cur.execute(sql, tuple(params))
    return cur.fetchall()


def products_in_category(category: str) -> List[tuple]:
    cur = get_cursor()
    like = f"%{category}%"
    cur.execute(
        "SELECT name, price FROM products WHERE category LIKE ?",
        (like,),
    )
    return cur.fetchall()


def price_of_product(name: str) -> List[tuple]:
    cur = get_cursor()
    like = f"%{name}%"
    cur.execute(
        "SELECT name, price FROM products WHERE name LIKE ? ORDER BY LENGTH(name) ASC LIMIT 5",
        (like,),
    )
    return cur.fetchall()
