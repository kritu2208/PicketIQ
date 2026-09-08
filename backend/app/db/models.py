"""SQLAlchemy ORM models for PicketIQ operational data layer.

Defines normalized relational models for the Olist Brazilian E-Commerce dataset:
- Customer
- Seller
- Product
- ProductCategoryTranslation
- Order
- OrderItem
- OrderPayment

Preserves foreign keys and relationship graphs without premature business metric definitions.
"""

from decimal import Decimal
from datetime import datetime, date
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Date,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
    JSON,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.session import Base


class Customer(Base):
    """Customer entity representing Brazilian e-commerce purchasers."""

    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_unique_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    customer_zip_code_prefix: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_city: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_state: Mapped[str] = mapped_column(String(5), nullable=False)

    # Relationships
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Customer(id='{self.customer_id}', city='{self.customer_city}', state='{self.customer_state}')>"


class Seller(Base):
    """Seller entity representing merchants fulfilling orders."""

    __tablename__ = "sellers"

    seller_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    seller_zip_code_prefix: Mapped[int] = mapped_column(Integer, nullable=False)
    seller_city: Mapped[str] = mapped_column(String(100), nullable=False)
    seller_state: Mapped[str] = mapped_column(String(5), nullable=False)

    # Relationships
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="seller",
    )

    def __repr__(self) -> str:
        return f"<Seller(id='{self.seller_id}', city='{self.seller_city}', state='{self.seller_state}')>"


class ProductCategoryTranslation(Base):
    """Translation lookup mapping Portuguese product categories to English."""

    __tablename__ = "product_category_translations"

    product_category_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    product_category_name_english: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<ProductCategoryTranslation('{self.product_category_name}' -> '{self.product_category_name_english}')>"


class Product(Base):
    """Product catalog item entity."""

    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_category_name: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    product_weight_g: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_length_cm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_height_cm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_width_cm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="product",
    )

    def __repr__(self) -> str:
        return f"<Product(id='{self.product_id}', category='{self.product_category_name}')>"


class Order(Base):
    """Order transaction record tracking purchase lifecycle and fulfillment status."""

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    order_status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    order_purchase_timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    order_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    order_delivered_carrier_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    order_delivered_customer_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    order_estimated_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="orders",
    )
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payments: Mapped[List["OrderPayment"]] = relationship(
        "OrderPayment",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Order(id='{self.order_id}', status='{self.order_status}', purchased_at='{self.order_purchase_timestamp}')>"


class OrderItem(Base):
    """Individual line item within an order, linking to product and fulfilling seller."""

    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        primary_key=True,
    )
    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("products.product_id"),
        index=True,
        nullable=False,
    )
    seller_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("sellers.seller_id"),
        index=True,
        nullable=False,
    )
    shipping_limit_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    freight_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="items",
    )
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="order_items",
    )
    seller: Mapped["Seller"] = relationship(
        "Seller",
        back_populates="order_items",
    )

    def __repr__(self) -> str:
        return f"<OrderItem(order_id='{self.order_id}', item_id={self.order_item_id}, price={self.price})>"


class OrderPayment(Base):
    """Payment transaction details for an order (credit card, boleto, voucher, debit)."""

    __tablename__ = "order_payments"

    order_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        primary_key=True,
    )
    payment_sequential: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="payments",
    )

    def __repr__(self) -> str:
        return (
            f"<OrderPayment(order_id='{self.order_id}', seq={self.payment_sequential}, "
            f"type='{self.payment_type}', value={self.payment_value})>"
        )


class KPIDaily(Base):
    """Aggregated daily business KPI metrics for analytical consumption and anomaly detection."""

    __tablename__ = "kpi_daily"
    __table_args__ = (
        UniqueConstraint("metric_name", "date", "segment", name="uq_kpi_metric_date_segment"),
        Index("ix_kpi_daily_metric_date", "metric_name", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    segment: Mapped[str] = mapped_column(String(50), nullable=False, default="all")

    def __repr__(self) -> str:
        return (
            f"<KPIDaily(metric='{self.metric_name}', date={self.date}, "
            f"segment='{self.segment}', value={self.value})>"
        )


class Anomaly(Base):
    """Statistical KPI anomaly record identified through rolling baseline deviation."""

    __tablename__ = "anomalies"
    __table_args__ = (
        UniqueConstraint("metric_name", "date", name="uq_anomaly_metric_date"),
        Index("ix_anomalies_metric_date", "metric_name", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expected_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    actual_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    z_score: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # "low", "medium", "high"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # "open", "investigating", "resolved"
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<Anomaly(metric='{self.metric_name}', date={self.date}, "
            f"actual={self.actual_value}, expected={self.expected_value}, "
            f"z={self.z_score}, severity='{self.severity}')>"
        )


class Investigation(Base):
    """Execution session of an automated investigation on a detected KPI anomaly."""

    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("anomalies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="in_progress")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    anomaly: Mapped["Anomaly"] = relationship("Anomaly", backref="investigations")
    evidence_logs: Mapped[List["InvestigationEvidence"]] = relationship(
        "InvestigationEvidence",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="InvestigationEvidence.step_number",
    )

    def __repr__(self) -> str:
        return (
            f"<Investigation(id={self.id}, anomaly_id={self.anomaly_id}, "
            f"status='{self.status}')>"
        )


class InvestigationEvidence(Base):
    """Structured evidence log entry captured during an investigation step."""

    __tablename__ = "investigation_evidence"
    __table_args__ = (
        UniqueConstraint("investigation_id", "step_number", name="uq_investigation_step"),
        Index("ix_investigation_evidence_anomaly", "anomaly_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    anomaly_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("anomalies.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    input_parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "success", "error"
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    investigation: Mapped["Investigation"] = relationship(
        "Investigation",
        back_populates="evidence_logs",
    )

    def __repr__(self) -> str:
        return (
            f"<InvestigationEvidence(id={self.id}, investigation_id={self.investigation_id}, "
            f"step={self.step_number}, tool='{self.tool_name}', status='{self.status}')>"
        )


class InvestigationConclusion(Base):
    """Evidence-grounded root-cause investigation conclusion produced by an LLM interpreter."""

    __tablename__ = "investigation_conclusions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    anomaly_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("anomalies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    root_cause: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)  # "high", "medium", "low"
    affected_segment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    evidence_references: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    validation_passed: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    investigation: Mapped["Investigation"] = relationship("Investigation", backref="conclusion")
    anomaly: Mapped["Anomaly"] = relationship("Anomaly")

    def __repr__(self) -> str:
        return (
            f"<InvestigationConclusion(id={self.id}, anomaly_id={self.anomaly_id}, "
            f"root_cause='{self.root_cause[:40]}...', confidence='{self.confidence}')>"
        )


__all__ = [
    "Base",
    "Customer",
    "Seller",
    "ProductCategoryTranslation",
    "Product",
    "Order",
    "OrderItem",
    "OrderPayment",
    "KPIDaily",
    "Anomaly",
    "Investigation",
    "InvestigationEvidence",
    "InvestigationConclusion",
]


