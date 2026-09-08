"""KPI Definition and Metadata Registry.

Provides structured, auditable metadata for core business metrics, documenting
exact business definitions, formula numerators/denominators, source tables,
date attribution rules, exclusions, and display units.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class KPIMetadata:
    """Metadata definition for a business metric."""

    name: str
    display_name: str
    description: str
    numerator: Optional[str]
    denominator: Optional[str]
    source_tables: List[str]
    date_attribution_rule: str
    exclusions: List[str]
    unit: str


KPI_DAILY_REVENUE = "daily_revenue"
KPI_ORDER_COUNT = "order_count"
KPI_AVERAGE_ORDER_VALUE = "average_order_value"
KPI_CANCELLATION_RATE = "cancellation_rate"
KPI_DELIVERY_DELAY_RATE = "delivery_delay_rate"

CORE_KPIS: List[str] = [
    KPI_DAILY_REVENUE,
    KPI_ORDER_COUNT,
    KPI_AVERAGE_ORDER_VALUE,
    KPI_CANCELLATION_RATE,
    KPI_DELIVERY_DELAY_RATE,
]

KPI_REGISTRY: Dict[str, KPIMetadata] = {
    KPI_DAILY_REVENUE: KPIMetadata(
        name=KPI_DAILY_REVENUE,
        display_name="Daily Revenue",
        description=(
            "Total monetary value of merchandise sold on the order purchase date, "
            "excluding cancelled and unavailable orders. Freight and payment installments are excluded."
        ),
        numerator="sum(order_items.price)",
        denominator=None,
        source_tables=["orders", "order_items"],
        date_attribution_rule="orders.order_purchase_timestamp",
        exclusions=[
            "orders with order_status in ('canceled', 'unavailable')",
            "order_items.freight_value",
            "order_payments.payment_value",
        ],
        unit="currency_brl",
    ),
    KPI_ORDER_COUNT: KPIMetadata(
        name=KPI_ORDER_COUNT,
        display_name="Order Count",
        description=(
            "Total number of distinct orders created on the order purchase date across all order statuses."
        ),
        numerator="count(distinct orders.order_id)",
        denominator=None,
        source_tables=["orders"],
        date_attribution_rule="orders.order_purchase_timestamp",
        exclusions=[],
        unit="count",
    ),
    KPI_AVERAGE_ORDER_VALUE: KPIMetadata(
        name=KPI_AVERAGE_ORDER_VALUE,
        display_name="Average Order Value (AOV)",
        description=(
            "Average monetary revenue generated per revenue-eligible order on the purchase date. "
            "Computed as daily_revenue divided by the count of revenue-eligible orders."
        ),
        numerator="daily_revenue",
        denominator="count(orders with order_status not in ('canceled', 'unavailable'))",
        source_tables=["orders", "order_items"],
        date_attribution_rule="orders.order_purchase_timestamp",
        exclusions=["orders with order_status in ('canceled', 'unavailable')"],
        unit="currency_brl",
    ),
    KPI_CANCELLATION_RATE: KPIMetadata(
        name=KPI_CANCELLATION_RATE,
        display_name="Cancellation Rate",
        description=(
            "Proportion of total orders placed on the purchase date that ended in a canceled status. "
            "Expressed as a decimal ratio between 0 and 1."
        ),
        numerator="count(orders with order_status = 'canceled')",
        denominator="total orders placed on purchase date",
        source_tables=["orders"],
        date_attribution_rule="orders.order_purchase_timestamp",
        exclusions=[],
        unit="ratio",
    ),
    KPI_DELIVERY_DELAY_RATE: KPIMetadata(
        name=KPI_DELIVERY_DELAY_RATE,
        display_name="Delivery Delay Rate",
        description=(
            "Proportion of delivered orders with known customer delivery and estimated delivery dates "
            "that arrived after the estimated delivery date (actual_delivery_date > estimated_delivery_date). "
            "Attributed to the original order purchase date."
        ),
        numerator="count(delivered orders where actual_delivery > estimated_delivery)",
        denominator="count(delivered orders with non-null actual and estimated delivery dates)",
        source_tables=["orders"],
        date_attribution_rule="orders.order_purchase_timestamp",
        exclusions=[
            "orders missing order_delivered_customer_date",
            "orders missing order_estimated_delivery_date",
            "non-delivered orders",
        ],
        unit="ratio",
    ),
}


def get_kpi_metadata(metric_name: str) -> Optional[KPIMetadata]:
    """Retrieve metadata for a specific KPI metric name."""
    return KPI_REGISTRY.get(metric_name)
