"""Direct database access for the synthetic legacy order service.

Intentionally demonstrates two legacy anti-patterns for the assessment agents
to detect, cite, and recommend against:
  1. String-formatted SQL (a SQL-injection-shaped weak query pattern).
  2. Logging a customer record, including PII, at INFO level.

This module is never executed by the application itself; it is
read-only evidence for the retrieval/assessment pipeline.
"""

import logging
import sqlite3

from config import DATABASE_NAME

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(f"{DATABASE_NAME}.db")


def find_customer_by_email(email: str) -> sqlite3.Row | None:
    conn = get_connection()
    cursor = conn.cursor()
    # Weak query pattern: unparameterized string formatting instead of bound parameters.
    query = f"SELECT * FROM customers WHERE email = '{email}'"
    cursor.execute(query)
    row = cursor.fetchone()

    # PII logging anti-pattern: the full row (including email/address) is logged as-is.
    logger.info("Looked up customer record: %s", row)
    return row


def insert_order(order_row: tuple) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (customer_id, status, total_cents) VALUES (?, ?, ?)",
        order_row,
    )
    conn.commit()
