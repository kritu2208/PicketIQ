"""Deterministic unit tests for Olist batch ingestion and relational data layer."""

import csv
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import (
    Customer,
    Seller,
    Product,
    Order,
    OrderItem,
    OrderPayment,
    ProductCategoryTranslation,
)
from app.ingestion.load_olist import (
    ingest_olist_data,
    IngestionValidationError,
    FILE_CUSTOMERS,
    FILE_SELLERS,
    FILE_PRODUCTS,
    FILE_ORDERS,
    FILE_ORDER_ITEMS,
    FILE_ORDER_PAYMENTS,
    FILE_CATEGORY_TRANSLATIONS,
)


@pytest.fixture
def db_session():
    """In-memory SQLite database session isolated per test."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def sample_olist_dir(tmp_path: Path) -> Path:
    """Creates a complete, valid sample Olist dataset directory."""
    data_dir = tmp_path / "olist"
    data_dir.mkdir(parents=True)

    # 1. Category translations
    trans_csv = data_dir / FILE_CATEGORY_TRANSLATIONS
    with open(trans_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["product_category_name", "product_category_name_english"])
        writer.writerow(["beleza_saude", "health_beauty"])
        writer.writerow(["informatica_acessorios", "computers_accessories"])

    # 2. Customers
    cust_csv = data_dir / FILE_CUSTOMERS
    with open(cust_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ])
        writer.writerow(["c_001", "u_001", "10001", "sao paulo", "SP"])
        writer.writerow(["c_002", "u_002", "20002", "rio de janeiro", "RJ"])

    # 3. Sellers
    sell_csv = data_dir / FILE_SELLERS
    with open(sell_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
        ])
        writer.writerow(["s_001", "13000", "campinas", "SP"])
        writer.writerow(["s_002", "80000", "curitiba", "PR"])

    # 4. Products
    prod_csv = data_dir / FILE_PRODUCTS
    with open(prod_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "product_id",
            "product_category_name",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ])
        writer.writerow(["p_001", "beleza_saude", "500", "20", "10", "15"])
        writer.writerow(["p_002", "informatica_acessorios", "1200", "30", "5", "25"])

    # 5. Orders
    order_csv = data_dir / FILE_ORDERS
    with open(order_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ])
        writer.writerow([
            "o_001",
            "c_001",
            "delivered",
            "2017-10-02 10:56:33",
            "2017-10-02 11:05:15",
            "2017-10-04 19:55:00",
            "2017-10-10 21:25:13",
            "2017-10-18 00:00:00",
        ])
        writer.writerow([
            "o_002",
            "c_002",
            "shipped",
            "2017-10-05 14:12:00",
            "2017-10-05 14:30:00",
            "2017-10-07 10:00:00",
            "",
            "2017-10-25 00:00:00",
        ])

    # 6. Order items
    items_csv = data_dir / FILE_ORDER_ITEMS
    with open(items_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ])
        writer.writerow(["o_001", "1", "p_001", "s_001", "2017-10-06 11:05:15", "29.99", "8.72"])
        writer.writerow(["o_001", "2", "p_002", "s_002", "2017-10-06 11:05:15", "119.50", "15.30"])
        writer.writerow(["o_002", "1", "p_002", "s_002", "2017-10-10 14:30:00", "125.00", "16.10"])

    # 7. Order payments
    pay_csv = data_dir / FILE_ORDER_PAYMENTS
    with open(pay_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ])
        writer.writerow(["o_001", "1", "credit_card", "3", "173.51"])
        writer.writerow(["o_002", "1", "boleto", "1", "141.10"])

    return data_dir


def test_missing_file_detection(tmp_path: Path, db_session):
    """Test that ingestion clearly fails when a required dataset CSV file is missing."""
    empty_dir = tmp_path / "empty_olist"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError) as exc_info:
        ingest_olist_data(empty_dir, db_session)

    error_msg = str(exc_info.value)
    assert "Missing required Olist CSV files" in error_msg
    assert FILE_ORDERS in error_msg
    assert FILE_CUSTOMERS in error_msg


def test_required_column_validation(sample_olist_dir: Path, db_session):
    """Test that missing required columns raise an IngestionValidationError identifying file and column."""
    # Corrupt orders CSV header by removing customer_id
    order_csv = sample_olist_dir / FILE_ORDERS
    with open(order_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "order_id",
            # "customer_id" is intentionally omitted
            "order_status",
            "order_purchase_timestamp",
        ])
        writer.writerow(["o_001", "delivered", "2017-10-02 10:56:33"])

    with pytest.raises(IngestionValidationError) as exc_info:
        ingest_olist_data(sample_olist_dir, db_session)

    err = exc_info.value
    assert err.file_name == FILE_ORDERS
    assert "customer_id" in err.column_name


def test_data_type_conversion(sample_olist_dir: Path, db_session):
    """Test that ingestion properly converts Decimal, DateTime, and integer values."""
    counts = ingest_olist_data(sample_olist_dir, db_session)
    assert counts["customers"] == 2
    assert counts["sellers"] == 2
    assert counts["products"] == 2
    assert counts["orders"] == 2
    assert counts["order_items"] == 3
    assert counts["order_payments"] == 2

    # Verify OrderItem monetary types are Decimal and timestamps are datetime
    item = db_session.execute(
        select(OrderItem).where(OrderItem.order_id == "o_001", OrderItem.order_item_id == 1)
    ).scalar_one()

    assert isinstance(item.price, Decimal)
    assert item.price == Decimal("29.99")
    assert isinstance(item.freight_value, Decimal)
    assert item.freight_value == Decimal("8.72")
    assert isinstance(item.shipping_limit_date, datetime)
    assert item.shipping_limit_date == datetime(2017, 10, 6, 11, 5, 15)

    # Verify Order nullable datetime fields
    order1 = db_session.execute(select(Order).where(Order.order_id == "o_001")).scalar_one()
    assert order1.order_delivered_customer_date == datetime(2017, 10, 10, 21, 25, 13)

    order2 = db_session.execute(select(Order).where(Order.order_id == "o_002")).scalar_one()
    assert order2.order_delivered_customer_date is None  # Nullable timestamp correctly handled


def test_invalid_timestamp_handling(sample_olist_dir: Path, db_session):
    """Test that malformed timestamp strings fail fast and identify row and column."""
    order_csv = sample_olist_dir / FILE_ORDERS
    with open(order_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ])
        writer.writerow([
            "o_001",
            "c_001",
            "delivered",
            "INVALID_DATE_TIME_STRING",
            "",
            "",
            "",
            "",
        ])

    with pytest.raises(IngestionValidationError) as exc_info:
        ingest_olist_data(sample_olist_dir, db_session)

    err = exc_info.value
    assert err.file_name == FILE_ORDERS
    assert err.column_name == "order_purchase_timestamp"
    assert err.row_number == 2
    assert "Invalid timestamp format" in err.reason


def test_invalid_numeric_handling(sample_olist_dir: Path, db_session):
    """Test that malformed numeric and monetary strings fail fast and identify row and column."""
    items_csv = sample_olist_dir / FILE_ORDER_ITEMS
    with open(items_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ])
        writer.writerow(["o_001", "1", "p_001", "s_001", "2017-10-06 11:05:15", "NOT_A_PRICE", "8.72"])

    with pytest.raises(IngestionValidationError) as exc_info:
        ingest_olist_data(sample_olist_dir, db_session)

    err = exc_info.value
    assert err.file_name == FILE_ORDER_ITEMS
    assert err.column_name == "price"
    assert err.row_number == 2
    assert "Unable to parse into valid Decimal number" in err.reason


def test_ingestion_idempotency(sample_olist_dir: Path, db_session):
    """Test that running batch ingestion multiple times does not produce duplicate records."""
    counts_first = ingest_olist_data(sample_olist_dir, db_session, clear_existing=True)
    counts_second = ingest_olist_data(sample_olist_dir, db_session, clear_existing=True)

    assert counts_first == counts_second

    # Verify counts in the actual database match exact expectation without duplication
    total_orders = len(db_session.execute(select(Order)).scalars().all())
    total_items = len(db_session.execute(select(OrderItem)).scalars().all())
    total_customers = len(db_session.execute(select(Customer)).scalars().all())

    assert total_orders == 2
    assert total_items == 3
    assert total_customers == 2


def test_relational_graph_integrity(sample_olist_dir: Path, db_session):
    """Test that ORM relationships across customers, orders, items, products, and sellers function properly."""
    ingest_olist_data(sample_olist_dir, db_session)

    order = db_session.execute(select(Order).where(Order.order_id == "o_001")).scalar_one()

    # Customer relationship
    assert order.customer.customer_city == "sao paulo"

    # Items relationship
    assert len(order.items) == 2
    first_item = order.items[0]
    assert first_item.product.product_id == "p_001"
    assert first_item.seller.seller_city == "campinas"

    # Payments relationship
    assert len(order.payments) == 1
    assert order.payments[0].payment_type == "credit_card"
    assert order.payments[0].payment_value == Decimal("173.51")
