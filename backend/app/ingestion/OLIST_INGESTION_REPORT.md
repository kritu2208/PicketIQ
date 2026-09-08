# Olist Production Ingestion Report

**PicketIQ — Autonomous Business Signal Investigation Platform**  
*Production Ingestion & Analytical Pipeline Verification Report*  
*Execution Date: 2026-09-04*

---

## Executive Summary

The official Olist Brazilian E-Commerce dataset has been successfully ingested into the PicketIQ PostgreSQL production database. The ingestion process loaded **451,535 records** across 7 relational tables with **zero data fabrication**, **zero records discarded**, **zero foreign-key orphans**, and **100% idempotency**. 

Downstream analytical smoke tests verified that the existing Phase 3 deterministic KPI engine and Phase 4 statistical rolling Z-score anomaly detector operate seamlessly on real production data.

---

## Source Dataset

* **Source Directory**: `c:\Users\91812\PicketIQ\data\olist\`
* **Integrity Status**: 100% unmodified raw CSVs; no intermediate or altered files created.
* **Encoding Handling**: Standard UTF-8 with BOM-safe `utf-8-sig` handling for `product_category_name_translation.csv`, ensuring header column `product_category_name` is cleanly parsed without byte artifact pollution.
* **Files Ingested**:
  1. `olist_customers_dataset.csv` (8.62 MB)
  2. `olist_sellers_dataset.csv` (0.17 MB)
  3. `olist_products_dataset.csv` (2.27 MB)
  4. `product_category_name_translation.csv` (0.003 MB)
  5. `olist_orders_dataset.csv` (16.84 MB)
  6. `olist_order_items_dataset.csv` (14.72 MB)
  7. `olist_order_payments_dataset.csv` (5.51 MB)

---

## Database Target

* **Database Engine**: PostgreSQL 16.6 (x64 Windows)
* **Host / Port**: `127.0.0.1:5433`
* **Database**: `picketiq`
* **Schema Definition**: Standard SQLAlchemy ORM declarative models (`Base.metadata.create_all`)
* **Tables Initialized**: 9 tables (`customers`, `sellers`, `product_category_translations`, `products`, `orders`, `order_items`, `order_payments`, `kpi_daily`, `anomalies`)

---

## Rows Ingested

Batch ingestion was executed in relational dependency order using chunked bulk mappings (10,000 records per chunk) with strict type conversions for dates, timestamps, integers, and `Decimal` financial values.

| Execution Step | Entity / Table Name | Source CSV File | Ingested Row Count |
|---|---|---|---|
| 1 | `customers` | `olist_customers_dataset.csv` | 99,441 |
| 2 | `sellers` | `olist_sellers_dataset.csv` | 3,095 |
| 3 | `products` | `olist_products_dataset.csv` | 32,951 |
| 4 | `product_category_translations` | `product_category_name_translation.csv` | 71 |
| 5 | `orders` | `olist_orders_dataset.csv` | 99,441 |
| 6 | `order_items` | `olist_order_items_dataset.csv` | 112,650 |
| 7 | `order_payments` | `olist_order_payments_dataset.csv` | 103,886 |
| **Total** | **All Entities** | **7 CSV Files** | **451,535** |

---

## Row Count Verification

Actual database counts queried directly from PostgreSQL (`SELECT COUNT(*) FROM <table>`) compared against the audited counts:

| Target Table | Expected Audited Count | Actual Database Count | Discrepancy | Verification Status |
|---|---|---|---|---|
| `customers` | 99,441 | **99,441** | 0 | **MATCH (100%)** |
| `sellers` | 3,095 | **3,095** | 0 | **MATCH (100%)** |
| `products` | 32,951 | **32,951** | 0 | **MATCH (100%)** |
| `product_category_translations` | 71 | **71** | 0 | **MATCH (100%)** |
| `orders` | 99,441 | **99,441** | 0 | **MATCH (100%)** |
| `order_items` | 112,650 | **112,650** | 0 | **MATCH (100%)** |
| `order_payments` | 103,886 | **103,886** | 0 | **MATCH (100%)** |
| **Total Operational Rows** | **451,535** | **451,535** | **0** | **MATCH (100%)** |

---

## Foreign Key Verification

Referential integrity was validated by testing for orphaned foreign key references across all operational tables:

| Foreign Key Relationship | SQL Orphan Query | Orphan Records Found | Integrity Status |
|---|---|---|---|
| `orders.customer_id -> customers.customer_id` | `SELECT COUNT(*) FROM orders o LEFT JOIN customers c ON o.customer_id = c.customer_id WHERE c.customer_id IS NULL` | **0** | **100.0% Valid** |
| `order_items.order_id -> orders.order_id` | `SELECT COUNT(*) FROM order_items oi LEFT JOIN orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL` | **0** | **100.0% Valid** |
| `order_items.product_id -> products.product_id` | `SELECT COUNT(*) FROM order_items oi LEFT JOIN products p ON oi.product_id = p.product_id WHERE p.product_id IS NULL` | **0** | **100.0% Valid** |
| `order_items.seller_id -> sellers.seller_id` | `SELECT COUNT(*) FROM order_items oi LEFT JOIN sellers s ON oi.seller_id = s.seller_id WHERE s.seller_id IS NULL` | **0** | **100.0% Valid** |
| `order_payments.order_id -> orders.order_id` | `SELECT COUNT(*) FROM order_payments op LEFT JOIN orders o ON op.order_id = o.order_id WHERE o.order_id IS NULL` | **0** | **100.0% Valid** |

Zero orphaned records exist across the entire operational relational schema.

---

## Null Preservation

All natural source nulls were strictly preserved without data fabrication or imputation:

1. **Orders Without Payments**:
   - Audited expectation: Exactly 1 order (`order_id = 'bfbd0f9bdef84302105ad712db648a6c'`).
   - Actual database state: Exactly **1 order** has no record in `order_payments`. Zero fabricated payment records were created.
2. **Missing Customer Delivery Dates**:
   - Audited expectation: 2,965 orders with `order_delivered_customer_date IS NULL` (canceled, in-transit, or processing orders).
   - Actual database state: Exactly **2,965 orders** have `NULL` delivery dates.
3. **Missing Product Categories**:
   - Audited expectation: 610 products with uncategorized catalog entries.
   - Actual database state: Exactly **610 products** have `product_category_name IS NULL`.
4. **Missing Product Physical Dimensions**:
   - Audited expectation: 2 products lacking dimensions (`product_weight_g`, `product_length_cm`, etc.).
   - Actual database state: Exactly **2 products** have `NULL` weight and dimensions.
5. **Untranslated Product Categories**:
   - Audited expectation: 13 products belong to 2 Portuguese categories not present in the translation dictionary (`portateis_cozinha_e_preparadores_de_alimentos` and `pc_gamer`).
   - Actual database state: Exactly **13 products** lack an English translation row. Zero translations were invented.

---

## Idempotency Verification

Ingestion was executed twice in succession against the target PostgreSQL database:
* **Run 1**: Initial load populated all 451,535 rows.
* **Run 2**: Complete batch ingestion re-executed with `clear_existing=True`.
* **Verification**:
  - `customers`: 99,441 rows (no duplicates)
  - `sellers`: 3,095 rows (no duplicates)
  - `products`: 32,951 rows (no duplicates)
  - `product_category_translations`: 71 rows (no duplicates)
  - `orders`: 99,441 rows (no duplicates)
  - `order_items`: 112,650 rows (no duplicates)
  - `order_payments`: 103,886 rows (no duplicates)
* Total row counts remained identical. No duplicate primary keys or inflated counts occurred.

---

## KPI Data Readiness

A smoke test of the Phase 3 deterministic KPI engine (`app.kpi.compute_kpis`) was conducted on the ingested real data:

* **Date Range Processed**: `2016-09-04` to `2018-10-17`
* **Dates Processed**: 634 active commercial dates
* **Total Daily KPI Records Generated**: **3,170 records** (634 dates × 5 metrics)
* **Core Metrics Computed**:
  1. `daily_revenue`: **Computes successfully** (Sum of item prices on purchase date, excluding canceled/unavailable orders)
  2. `order_count`: **Computes successfully** (Daily count of orders placed)
  3. `average_order_value`: **Computes successfully** (`daily_revenue / eligible_orders`)
  4. `cancellation_rate`: **Computes successfully** (`canceled_orders / total_orders`)
  5. `delivery_delay_rate`: **Computes successfully** (`delayed_orders / delivered_orders_with_valid_dates`)
* **Precision**: All values persisted with exact 4-decimal place fixed-point Decimal representation (`Numeric(14, 4)`).

---

## Anomaly Detection Readiness

A smoke test of the Phase 4 rolling Z-score statistical anomaly detector (`app.detection.zscore_detector`) was executed with production defaults (`threshold = 3.0`, `window = 14`, `min_history = 7`):

* **Date Range Evaluated**: `2016-09-04` to `2018-10-17`
* **Metrics Processed**: 5 core metrics
* **Total KPI Observations Evaluated**: **3,135 observations**
* **Total Anomalies Detected**: **78 anomalies**
* **Severity Distribution**:
  - **Low Severity** ($3.0 \le |z| < 4.0$): **43**
  - **Medium Severity** ($4.0 \le |z| < 5.0$): **17**
  - **High Severity** ($|z| \ge 5.0$): **18**
* **Anomalies by Metric**:
  - `cancellation_rate`: 26 anomalies (7 High, 7 Medium, 12 Low)
  - `delivery_delay_rate`: 19 anomalies (2 High, 4 Medium, 13 Low)
  - `average_order_value`: 13 anomalies (4 High, 3 Medium, 6 Low)
  - `daily_revenue`: 12 anomalies (3 High, 2 Medium, 7 Low)
  - `order_count`: 8 anomalies (2 High, 1 Medium, 5 Low)
* **Key Historical Signal Observed**: Black Friday on `2017-11-24` flagged as a **High Severity** spike across both `order_count` (Actual: 1,176 orders vs Baseline: 196.6, $z = +26.82$) and `daily_revenue` (Actual: R$ 152,653.74 vs Baseline: R$ 27,628.63, $z = +15.87$).

---

## Test Suite Verification

The full pytest test suite was executed against the project:
* **Command**: `.\venv\Scripts\pytest -v`
* **Total Tests**: 42 tests
* **Passed**: **42 / 42 (100%)**
* **Failures / Errors**: 0

---

## Final Verdict

> **VERDICT: PRODUCTION INGESTION COMPLETE & VERIFIED**
>
> The real Olist dataset has been ingested into PostgreSQL with 100% fidelity to the audited source data. Relational graphs are complete and valid with zero orphan records. Both the KPI intelligence layer and statistical anomaly detection layer function properly on real production data. PicketIQ is fully prepared for subsequent investigative and analytical capabilities.
