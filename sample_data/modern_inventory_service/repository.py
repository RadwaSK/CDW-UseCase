"""Data access for the synthetic modern inventory service.

Queries are parameterized and logs carry only non-identifying identifiers, per
the security standard.
"""

import logging

import psycopg

from config import DATABASE_URL

logger = logging.getLogger(__name__)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def find_item_by_sku(sku: str) -> tuple | None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT sku, name, quantity FROM items WHERE sku = %s", (sku,))
        row = cursor.fetchone()

    # Logs the lookup key only — never a customer or PII-bearing record.
    logger.info("item_lookup", extra={"sku": sku, "found": row is not None})
    return row


def adjust_quantity(sku: str, delta: int) -> None:
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE items SET quantity = quantity + %s WHERE sku = %s", (delta, sku)
        )
        conn.commit()
