"""Batch KPI Computation Engine.

Computes core daily business KPIs from operational relational tables:
1. daily_revenue
2. order_count
3. average_order_value
4. cancellation_rate
5. delivery_delay_rate

Persists results into `kpi_daily` with strict idempotency and decimal precision.
"""

import argparse
import logging
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import select, func, case, and_, delete, Date
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.db.models import Order, OrderItem, KPIDaily
from app.kpi.metadata import (
    CORE_KPIS,
    KPI_DAILY_REVENUE,
    KPI_ORDER_COUNT,
    KPI_AVERAGE_ORDER_VALUE,
    KPI_CANCELLATION_RATE,
    KPI_DELIVERY_DELAY_RATE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("picket_iq.kpi.compute")

FOUR_PLACES = Decimal("0.0001")


def quantize_value(val: Decimal) -> Decimal:
    """Format decimal value to 4 decimal places with standard half-up rounding."""
    return val.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def parse_cli_date(date_str: Optional[str]) -> Optional[date]:
    """Parse YYYY-MM-DD string into a date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.")


def get_available_date_range(session: Session) -> Tuple[Optional[date], Optional[date]]:
    """Determine the minimum and maximum order purchase dates present in the database."""
    date_expr = func.date(Order.order_purchase_timestamp)
    min_val = session.execute(select(func.min(date_expr))).scalar()
    max_val = session.execute(select(func.max(date_expr))).scalar()

    if not min_val or not max_val:
        return None, None

    min_date = min_val if isinstance(min_val, date) else date.fromisoformat(str(min_val))
    max_date = max_val if isinstance(max_val, date) else date.fromisoformat(str(max_val))
    return min_date, max_date


def compute_kpis_for_range(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    segment: str = "all",
) -> Dict[str, Any]:
    """Compute and persist daily business KPIs for the given date range.

    Args:
        session: Active SQLAlchemy Session instance.
        start_date: Starting date inclusive. Defaults to earliest order date.
        end_date: Ending date inclusive. Defaults to latest order date.
        segment: Business segment dimension. Defaults to 'all'.

    Returns:
        Summary dict containing date range, dates processed, and records written.
    """
    # 1. Resolve date boundaries if not provided
    avail_min, avail_max = get_available_date_range(session)
    if avail_min is None or avail_max is None:
        logger.warning("No orders found in database. KPI computation skipped.")
        return {
            "start_date": None,
            "end_date": None,
            "dates_processed": 0,
            "records_written": 0,
            "kpis": CORE_KPIS,
        }

    resolved_start = start_date or avail_min
    resolved_end = end_date or avail_max

    if resolved_start > resolved_end:
        raise ValueError(
            f"start_date ({resolved_start}) cannot be after end_date ({resolved_end})."
        )

    logger.info(
        "Computing KPIs from %s to %s for segment '%s'...",
        resolved_start,
        resolved_end,
        segment,
    )

    date_expr = func.date(Order.order_purchase_timestamp)
    date_filters = [
        date_expr >= resolved_start.isoformat(),
        date_expr <= resolved_end.isoformat(),
    ]

    # 2. Aggregation Query 1: Order-level metrics grouped by purchase date
    # Attributes: total orders, canceled orders, revenue-eligible orders, delivered orders with dates, delayed orders
    order_stmt = (
        select(
            date_expr.label("purchase_date"),
            func.count(Order.order_id).label("total_orders"),
            func.count(case((Order.order_status == "canceled", 1))).label("canceled_orders"),
            func.count(
                case((~Order.order_status.in_(["canceled", "unavailable"]), 1))
            ).label("eligible_orders"),
            func.count(
                case(
                    (
                        and_(
                            Order.order_delivered_customer_date.isnot(None),
                            Order.order_estimated_delivery_date.isnot(None),
                        ),
                        1,
                    )
                )
            ).label("delivered_with_dates"),
            func.count(
                case(
                    (
                        and_(
                            Order.order_delivered_customer_date.isnot(None),
                            Order.order_estimated_delivery_date.isnot(None),
                            Order.order_delivered_customer_date > Order.order_estimated_delivery_date,
                        ),
                        1,
                    )
                )
            ).label("delayed_orders"),
        )
        .where(and_(*date_filters))
        .group_by(date_expr)
    )
    order_rows = session.execute(order_stmt).all()

    # 3. Aggregation Query 2: Item-level revenue grouped by purchase date
    # Sums order_items.price for revenue-eligible orders
    revenue_stmt = (
        select(
            date_expr.label("purchase_date"),
            func.sum(OrderItem.price).label("revenue"),
        )
        .join(OrderItem, Order.order_id == OrderItem.order_id)
        .where(
            and_(
                ~Order.order_status.in_(["canceled", "unavailable"]),
                *date_filters,
            )
        )
        .group_by(date_expr)
    )
    revenue_rows = session.execute(revenue_stmt).all()

    # Map revenue by normalized date string
    revenue_by_date: Dict[str, Decimal] = {}
    for dt_val, rev in revenue_rows:
        dt_str = dt_val if isinstance(dt_val, str) else dt_val.isoformat()
        revenue_by_date[dt_str] = Decimal(str(rev)) if rev is not None else Decimal("0.00")

    # 4. Assemble KPI daily records
    records_to_insert: List[KPIDaily] = []
    processed_dates: List[date] = []

    for row in order_rows:
        raw_dt, total_orders, canceled_orders, eligible_orders, delivered_with_dates, delayed_orders = row
        dt_obj = date.fromisoformat(str(raw_dt))
        dt_str = dt_obj.isoformat()
        processed_dates.append(dt_obj)

        # 1. daily_revenue
        revenue = revenue_by_date.get(dt_str, Decimal("0.00"))
        records_to_insert.append(
            KPIDaily(
                metric_name=KPI_DAILY_REVENUE,
                date=dt_obj,
                value=quantize_value(revenue),
                segment=segment,
            )
        )

        # 2. order_count
        records_to_insert.append(
            KPIDaily(
                metric_name=KPI_ORDER_COUNT,
                date=dt_obj,
                value=quantize_value(Decimal(total_orders)),
                segment=segment,
            )
        )

        # 3. average_order_value (AOV = daily_revenue / eligible_orders)
        if eligible_orders > 0:
            aov = revenue / Decimal(eligible_orders)
        else:
            aov = Decimal("0.00")
        records_to_insert.append(
            KPIDaily(
                metric_name=KPI_AVERAGE_ORDER_VALUE,
                date=dt_obj,
                value=quantize_value(aov),
                segment=segment,
            )
        )

        # 4. cancellation_rate (canceled_orders / total_orders)
        if total_orders > 0:
            cancel_rate = Decimal(canceled_orders) / Decimal(total_orders)
        else:
            cancel_rate = Decimal("0.00")
        records_to_insert.append(
            KPIDaily(
                metric_name=KPI_CANCELLATION_RATE,
                date=dt_obj,
                value=quantize_value(cancel_rate),
                segment=segment,
            )
        )

        # 5. delivery_delay_rate (delayed_orders / delivered_with_dates)
        if delivered_with_dates > 0:
            delay_rate = Decimal(delayed_orders) / Decimal(delivered_with_dates)
        else:
            delay_rate = Decimal("0.00")
        records_to_insert.append(
            KPIDaily(
                metric_name=KPI_DELIVERY_DELAY_RATE,
                date=dt_obj,
                value=quantize_value(delay_rate),
                segment=segment,
            )
        )

    # 5. Idempotent database write: delete existing range records and insert fresh calculations
    with session.begin_nested():
        session.execute(
            delete(KPIDaily).where(
                and_(
                    KPIDaily.date >= resolved_start,
                    KPIDaily.date <= resolved_end,
                    KPIDaily.segment == segment,
                    KPIDaily.metric_name.in_(CORE_KPIS),
                )
            )
        )
        session.add_all(records_to_insert)

    session.commit()

    logger.info(
        "Successfully wrote %d KPI records across %d dates.",
        len(records_to_insert),
        len(processed_dates),
    )

    return {
        "start_date": resolved_start,
        "end_date": resolved_end,
        "dates_processed": len(processed_dates),
        "records_written": len(records_to_insert),
        "kpis": CORE_KPIS,
    }


def main() -> None:
    """CLI entrypoint for batch KPI computation."""
    parser = argparse.ArgumentParser(
        description="Compute daily business KPIs from PicketIQ relational tables."
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format (default: earliest order purchase date)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date in YYYY-MM-DD format (default: latest order purchase date)",
    )
    parser.add_argument(
        "--segment",
        type=str,
        default="all",
        help="Segment identifier (default: all)",
    )
    args = parser.parse_args()

    try:
        start_dt = parse_cli_date(args.start_date)
        end_dt = parse_cli_date(args.end_date)
    except ValueError as err:
        logger.error(str(err))
        sys.exit(1)

    session = SessionLocal()
    try:
        summary = compute_kpis_for_range(
            session=session,
            start_date=start_dt,
            end_date=end_dt,
            segment=args.segment,
        )

        print("\n========================================")
        print("       PicketIQ KPI Computation         ")
        print("========================================")
        print(f"Date Range:       {summary['start_date']} to {summary['end_date']}")
        print(f"Segment:          {args.segment}")
        print(f"Dates Processed:  {summary['dates_processed']}")
        print(f"Records Written:  {summary['records_written']}")
        print("Metrics Computed:")
        for kpi in summary["kpis"]:
            print(f"  - {kpi}")
        print("========================================\n")
    except Exception as exc:
        session.rollback()
        logger.error("KPI computation failed: %s", exc)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
