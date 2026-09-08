"""Olist E-Commerce dataset batch ingestion module.

Validates, transforms, and loads Olist CSV datasets into relational PostgreSQL tables.
Maintains relational integrity, strict numeric precision, and idempotency.
"""

import argparse
import csv
import logging
import sys
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.db.session import SessionLocal, engine
from app.db.models import (
    Customer,
    Seller,
    ProductCategoryTranslation,
    Product,
    Order,
    OrderItem,
    OrderPayment,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("picket_iq.ingestion")

# Standard default data directory: PicketIQ/data/olist
DEFAULT_DATA_DIR = BASE_DIR.parent / "data" / "olist"

# Expected Olist file names
FILE_CUSTOMERS = "olist_customers_dataset.csv"
FILE_SELLERS = "olist_sellers_dataset.csv"
FILE_PRODUCTS = "olist_products_dataset.csv"
FILE_ORDERS = "olist_orders_dataset.csv"
FILE_ORDER_ITEMS = "olist_order_items_dataset.csv"
FILE_ORDER_PAYMENTS = "olist_order_payments_dataset.csv"
FILE_CATEGORY_TRANSLATIONS = "product_category_name_translation.csv"

REQUIRED_FILES = [
    FILE_CUSTOMERS,
    FILE_SELLERS,
    FILE_PRODUCTS,
    FILE_ORDERS,
    FILE_ORDER_ITEMS,
    FILE_ORDER_PAYMENTS,
]

REQUIRED_COLUMNS: Dict[str, List[str]] = {
    FILE_CUSTOMERS: [
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ],
    FILE_SELLERS: [
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ],
    FILE_PRODUCTS: [
        "product_id",
        "product_category_name",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ],
    FILE_ORDERS: [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    FILE_ORDER_ITEMS: [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ],
    FILE_ORDER_PAYMENTS: [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ],
    FILE_CATEGORY_TRANSLATIONS: [
        "product_category_name",
        "product_category_name_english",
    ],
}


class IngestionValidationError(ValueError):
    """Raised when data validation fails during batch ingestion."""

    def __init__(
        self,
        file_name: str,
        column_name: str,
        row_number: int,
        raw_value: Any,
        reason: str,
    ):
        self.file_name = file_name
        self.column_name = column_name
        self.row_number = row_number
        self.raw_value = raw_value
        self.reason = reason
        super().__init__(
            f"Validation failed in '{file_name}' at row {row_number}, column '{column_name}': "
            f"{reason} (received: {raw_value!r})"
        )


def parse_decimal(
    raw_value: Optional[str],
    column_name: str,
    row_number: int,
    file_name: str,
    nullable: bool = False,
) -> Optional[Decimal]:
    """Parse string value into strict Decimal precision without floating-point inaccuracies."""
    if raw_value is None or raw_value.strip() == "":
        if nullable:
            return None
        raise IngestionValidationError(
            file_name, column_name, row_number, raw_value, "Required numeric value is missing or empty"
        )
    try:
        return Decimal(raw_value.strip())
    except (InvalidOperation, ValueError):
        raise IngestionValidationError(
            file_name, column_name, row_number, raw_value, "Unable to parse into valid Decimal number"
        )


def parse_int(
    raw_value: Optional[str],
    column_name: str,
    row_number: int,
    file_name: str,
    nullable: bool = False,
) -> Optional[int]:
    """Parse string value into integer, handling optional float-formatted integers like '123.0'."""
    if raw_value is None or raw_value.strip() == "":
        if nullable:
            return None
        raise IngestionValidationError(
            file_name, column_name, row_number, raw_value, "Required integer value is missing or empty"
        )
    try:
        val = raw_value.strip()
        # Handle string floats that represent integers (e.g. '123.0')
        if "." in val:
            return int(float(val))
        return int(val)
    except (ValueError, OverflowError):
        raise IngestionValidationError(
            file_name, column_name, row_number, raw_value, "Unable to parse into valid integer"
        )


BATCH_SIZE = 10000


def _bulk_insert(session: Session, model: Any, records: List[Dict[str, Any]], batch_size: int = BATCH_SIZE) -> None:
    """Insert records in chunks to optimize memory and query execution."""
    if not records:
        return
    for i in range(0, len(records), batch_size):
        session.bulk_insert_mappings(model, records[i : i + batch_size])


def parse_datetime(
    raw_value: Optional[str],
    column_name: str,
    row_number: int,
    file_name: str,
    nullable: bool = False,
) -> Optional[datetime]:
    """Parse string value into Python datetime with standard format support."""
    if raw_value is None or raw_value.strip() == "":
        if nullable:
            return None
        raise IngestionValidationError(
            file_name, column_name, row_number, raw_value, "Required timestamp is missing or empty"
        )
    val = raw_value.strip()
    # Fast path for ISO-formatted timestamps
    try:
        return datetime.fromisoformat(val)
    except ValueError:
        pass
    # Support common formats: 'YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DDTHH:MM:SS', 'YYYY-MM-DD'
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    raise IngestionValidationError(
        file_name, column_name, row_number, raw_value, "Invalid timestamp format (expected YYYY-MM-DD HH:MM:SS)"
    )


def validate_file_columns(file_path: Path, expected_columns: List[str]) -> None:
    """Validate that all required columns are present in the CSV file header."""
    file_name = file_path.name
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise IngestionValidationError(
                file_name, "header", 1, "", "CSV file is completely empty"
            )

    header_clean = [col.strip() for col in header]
    missing = [col for col in expected_columns if col not in header_clean]
    if missing:
        raise IngestionValidationError(
            file_name,
            ", ".join(missing),
            1,
            header_clean,
            f"CSV is missing required columns: {', '.join(missing)}",
        )


def verify_dataset_directory(data_dir: Path) -> None:
    """Verify that the data directory exists and all required Olist files are present."""
    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(
            f"Olist dataset directory not found: '{data_dir.resolve()}'. "
            "Please create the directory and place the Olist CSV files within it."
        )

    missing_files = [fname for fname in REQUIRED_FILES if not (data_dir / fname).exists()]
    if missing_files:
        raise FileNotFoundError(
            f"Missing required Olist CSV files in '{data_dir.resolve()}': {', '.join(missing_files)}"
        )


def load_category_translations(file_path: Path, session: Session) -> int:
    """Load product category translations if the translation CSV exists."""
    file_name = file_path.name
    validate_file_columns(file_path, REQUIRED_COLUMNS[file_name])

    records: List[Dict[str, Any]] = []
    seen_keys = set()
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            category = (row.get("product_category_name") or "").strip()
            english = (row.get("product_category_name_english") or "").strip()
            if not category:
                raise IngestionValidationError(
                    file_name, "product_category_name", row_num, category, "Primary key cannot be empty"
                )
            if category in seen_keys:
                continue
            seen_keys.add(category)
            records.append({
                "product_category_name": category,
                "product_category_name_english": english,
            })

    if records:
        _bulk_insert(session, ProductCategoryTranslation, records)
    return len(records)


def load_customers(file_path: Path, session: Session) -> int:
    """Load customer records from olist_customers_dataset.csv."""
    file_name = file_path.name
    validate_file_columns(file_path, REQUIRED_COLUMNS[file_name])

    records: List[Dict[str, Any]] = []
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            cid = (row.get("customer_id") or "").strip()
            uid = (row.get("customer_unique_id") or "").strip()
            if not cid:
                raise IngestionValidationError(file_name, "customer_id", row_num, cid, "Primary key cannot be empty")
            if not uid:
                raise IngestionValidationError(file_name, "customer_unique_id", row_num, uid, "Unique ID cannot be empty")

            zip_code = parse_int(row.get("customer_zip_code_prefix"), "customer_zip_code_prefix", row_num, file_name)
            city = (row.get("customer_city") or "").strip()
            state = (row.get("customer_state") or "").strip()

            records.append({
                "customer_id": cid,
                "customer_unique_id": uid,
                "customer_zip_code_prefix": zip_code,
                "customer_city": city,
                "customer_state": state,
            })

    if records:
        _bulk_insert(session, Customer, records)
    return len(records)


def load_sellers(file_path: Path, session: Session) -> int:
    """Load seller records from olist_sellers_dataset.csv."""
    file_name = file_path.name
    validate_file_columns(file_path, REQUIRED_COLUMNS[file_name])

    records: List[Dict[str, Any]] = []
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            sid = (row.get("seller_id") or "").strip()
            if not sid:
                raise IngestionValidationError(file_name, "seller_id", row_num, sid, "Primary key cannot be empty")

            zip_code = parse_int(row.get("seller_zip_code_prefix"), "seller_zip_code_prefix", row_num, file_name)
            city = (row.get("seller_city") or "").strip()
            state = (row.get("seller_state") or "").strip()

            records.append({
                "seller_id": sid,
                "seller_zip_code_prefix": zip_code,
                "seller_city": city,
                "seller_state": state,
            })

    if records:
        _bulk_insert(session, Seller, records)
    return len(records)


def load_products(file_path: Path, session: Session) -> int:
    """Load product catalog records from olist_products_dataset.csv."""
    file_name = file_path.name
    validate_file_columns(file_path, REQUIRED_COLUMNS[file_name])

    records: List[Dict[str, Any]] = []
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            pid = (row.get("product_id") or "").strip()
            if not pid:
                raise IngestionValidationError(file_name, "product_id", row_num, pid, "Primary key cannot be empty")

            cat_name = (row.get("product_category_name") or "").strip() or None
            weight = parse_int(row.get("product_weight_g"), "product_weight_g", row_num, file_name, nullable=True)
            length = parse_int(row.get("product_length_cm"), "product_length_cm", row_num, file_name, nullable=True)
            height = parse_int(row.get("product_height_cm"), "product_height_cm", row_num, file_name, nullable=True)
            width = parse_int(row.get("product_width_cm"), "product_width_cm", row_num, file_name, nullable=True)

            records.append({
                "product_id": pid,
                "product_category_name": cat_name,
                "product_weight_g": weight,
                "product_length_cm": length,
                "product_height_cm": height,
                "product_width_cm": width,
            })

    if records:
        _bulk_insert(session, Product, records)
    return len(records)


def load_orders(file_path: Path, session: Session) -> int:
    """Load orders from olist_orders_dataset.csv."""
    file_name = file_path.name
    validate_file_columns(file_path, REQUIRED_COLUMNS[file_name])

    records: List[Dict[str, Any]] = []
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            oid = (row.get("order_id") or "").strip()
            cid = (row.get("customer_id") or "").strip()
            status = (row.get("order_status") or "").strip()

            if not oid:
                raise IngestionValidationError(file_name, "order_id", row_num, oid, "Primary key cannot be empty")
            if not cid:
                raise IngestionValidationError(file_name, "customer_id", row_num, cid, "Customer ID foreign key cannot be empty")
            if not status:
                raise IngestionValidationError(file_name, "order_status", row_num, status, "Order status cannot be empty")

            purchase_ts = parse_datetime(row.get("order_purchase_timestamp"), "order_purchase_timestamp", row_num, file_name)
            approved_at = parse_datetime(row.get("order_approved_at"), "order_approved_at", row_num, file_name, nullable=True)
            delivered_carrier = parse_datetime(
                row.get("order_delivered_carrier_date"), "order_delivered_carrier_date", row_num, file_name, nullable=True
            )
            delivered_customer = parse_datetime(
                row.get("order_delivered_customer_date"), "order_delivered_customer_date", row_num, file_name, nullable=True
            )
            est_delivery = parse_datetime(
                row.get("order_estimated_delivery_date"), "order_estimated_delivery_date", row_num, file_name, nullable=True
            )

            records.append({
                "order_id": oid,
                "customer_id": cid,
                "order_status": status,
                "order_purchase_timestamp": purchase_ts,
                "order_approved_at": approved_at,
                "order_delivered_carrier_date": delivered_carrier,
                "order_delivered_customer_date": delivered_customer,
                "order_estimated_delivery_date": est_delivery,
            })

    if records:
        _bulk_insert(session, Order, records)
    return len(records)


def load_order_items(file_path: Path, session: Session) -> int:
    """Load order line items from olist_order_items_dataset.csv."""
    file_name = file_path.name
    validate_file_columns(file_path, REQUIRED_COLUMNS[file_name])

    records: List[Dict[str, Any]] = []
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            oid = (row.get("order_id") or "").strip()
            item_id = parse_int(row.get("order_item_id"), "order_item_id", row_num, file_name)
            pid = (row.get("product_id") or "").strip()
            sid = (row.get("seller_id") or "").strip()

            if not oid:
                raise IngestionValidationError(file_name, "order_id", row_num, oid, "Order ID cannot be empty")
            if not pid:
                raise IngestionValidationError(file_name, "product_id", row_num, pid, "Product ID cannot be empty")
            if not sid:
                raise IngestionValidationError(file_name, "seller_id", row_num, sid, "Seller ID cannot be empty")

            shipping_limit = parse_datetime(row.get("shipping_limit_date"), "shipping_limit_date", row_num, file_name)
            price = parse_decimal(row.get("price"), "price", row_num, file_name)
            freight = parse_decimal(row.get("freight_value"), "freight_value", row_num, file_name)

            records.append({
                "order_id": oid,
                "order_item_id": item_id,
                "product_id": pid,
                "seller_id": sid,
                "shipping_limit_date": shipping_limit,
                "price": price,
                "freight_value": freight,
            })

    if records:
        _bulk_insert(session, OrderItem, records)
    return len(records)


def load_order_payments(file_path: Path, session: Session) -> int:
    """Load payment records from olist_order_payments_dataset.csv."""
    file_name = file_path.name
    validate_file_columns(file_path, REQUIRED_COLUMNS[file_name])

    records: List[Dict[str, Any]] = []
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            oid = (row.get("order_id") or "").strip()
            seq = parse_int(row.get("payment_sequential"), "payment_sequential", row_num, file_name)
            ptype = (row.get("payment_type") or "").strip()
            installments = parse_int(row.get("payment_installments"), "payment_installments", row_num, file_name)
            pvalue = parse_decimal(row.get("payment_value"), "payment_value", row_num, file_name)

            if not oid:
                raise IngestionValidationError(file_name, "order_id", row_num, oid, "Order ID cannot be empty")
            if not ptype:
                raise IngestionValidationError(file_name, "payment_type", row_num, ptype, "Payment type cannot be empty")

            records.append({
                "order_id": oid,
                "payment_sequential": seq,
                "payment_type": ptype,
                "payment_installments": installments,
                "payment_value": pvalue,
            })

    if records:
        _bulk_insert(session, OrderPayment, records)
    return len(records)


def clear_existing_data(session: Session) -> None:
    """Clear existing tables in reverse foreign key order for clean, idempotent reloads."""
    logger.info("Clearing existing Olist operational records...")
    session.execute(delete(OrderPayment))
    session.execute(delete(OrderItem))
    session.execute(delete(Order))
    session.execute(delete(ProductCategoryTranslation))
    session.execute(delete(Product))
    session.execute(delete(Seller))
    session.execute(delete(Customer))
    session.flush()
    logger.info("Existing operational tables cleared.")


def ingest_olist_data(
    data_dir: Path,
    session: Session,
    clear_existing: bool = True,
) -> Dict[str, int]:
    """Execute complete Olist dataset validation and batch ingestion.

    Args:
        data_dir: Directory containing the Olist CSV files.
        session: Active SQLAlchemy Session instance.
        clear_existing: If True, clears existing tables before insertion ensuring idempotency.

    Returns:
        Dict mapping table names to the number of rows successfully inserted.
    """
    logger.info("Starting Olist batch ingestion from '%s'...", data_dir.resolve())
    verify_dataset_directory(data_dir)

    counts: Dict[str, int] = {}

    if clear_existing:
        clear_existing_data(session)

    # 1. Customers
    logger.info("Ingesting customers...")
    cnt = load_customers(data_dir / FILE_CUSTOMERS, session)
    counts["customers"] = cnt
    logger.info("Loaded %d customer records.", cnt)

    # 2. Sellers
    logger.info("Ingesting sellers...")
    cnt = load_sellers(data_dir / FILE_SELLERS, session)
    counts["sellers"] = cnt
    logger.info("Loaded %d seller records.", cnt)

    # 3. Products
    logger.info("Ingesting products...")
    cnt = load_products(data_dir / FILE_PRODUCTS, session)
    counts["products"] = cnt
    logger.info("Loaded %d product records.", cnt)

    # 4. Product category translations (optional lookup)
    trans_file = data_dir / FILE_CATEGORY_TRANSLATIONS
    if trans_file.exists():
        logger.info("Ingesting product category translations...")
        cnt = load_category_translations(trans_file, session)
        counts["product_category_translations"] = cnt
        logger.info("Loaded %d category translation records.", cnt)

    # 5. Orders
    logger.info("Ingesting orders...")
    cnt = load_orders(data_dir / FILE_ORDERS, session)
    counts["orders"] = cnt
    logger.info("Loaded %d order records.", cnt)

    # 6. Order items
    logger.info("Ingesting order line items...")
    cnt = load_order_items(data_dir / FILE_ORDER_ITEMS, session)
    counts["order_items"] = cnt
    logger.info("Loaded %d order item records.", cnt)

    # 7. Order payments
    logger.info("Ingesting order payments...")
    cnt = load_order_payments(data_dir / FILE_ORDER_PAYMENTS, session)
    counts["order_payments"] = cnt
    logger.info("Loaded %d order payment records.", cnt)

    session.commit()
    logger.info("Batch ingestion completed successfully: %s", counts)
    return counts


def main() -> None:
    """CLI entrypoint for batch ingestion script."""
    parser = argparse.ArgumentParser(
        description="PicketIQ Olist Dataset Batch Ingestion Tool"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Path to directory containing Olist CSV files (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--no-clear",
        action="store_false",
        dest="clear_existing",
        help="Do not clear existing records before insertion.",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        counts = ingest_olist_data(
            data_dir=args.data_dir,
            session=session,
            clear_existing=args.clear_existing,
        )
        print("\n--- Ingestion Summary ---")
        for table, count in counts.items():
            print(f"  {table}: {count:,} records")
        print("-------------------------\n")
    except Exception as exc:
        session.rollback()
        logger.error("Ingestion failed: %s", exc)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
