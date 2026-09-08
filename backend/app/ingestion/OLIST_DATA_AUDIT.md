# Olist Data Audit

**PicketIQ — Autonomous Business Signal Investigation Platform**  
*Read-Only Audit Checkpoint of Raw Olist Brazilian E-Commerce Dataset*  
*Audit Execution Date: 2026-09-04*

---

## Executive Summary

A comprehensive, non-destructive data quality audit was conducted on the official Olist Brazilian E-Commerce dataset located in `data/olist/`. All 7 required dataset files were parsed, verified, and statistically audited across schema conformance, null rates, key uniqueness, referential integrity, temporal consistency, financial validity, and compatibility with PicketIQ's analytical architecture.

### Key Audit Findings
1. **Total Volume & Completeness**: The dataset comprises **451,535 records** across 7 files. Key business entities include **99,441 orders**, **99,441 customer records** (96,096 unique buyers), **3,095 sellers**, **32,951 products**, **112,650 order items**, and **103,886 payment transactions**.
2. **Zero Primary Key Collisions**: There are **0 duplicate primary keys** across all files (`customer_id`, `seller_id`, `product_id`, `order_id`, `(order_id, order_item_id)`, `(order_id, payment_sequential)`, and `product_category_name`).
3. **Flawless Core Relational Integrity**: **0 orphan records** were detected across all core foreign-key relationships. Every single order references a valid customer; every order item references a valid order, product, and seller; and every payment references a valid order.
4. **Encoding Caveat (UTF-8 BOM)**: `product_category_name_translation.csv` contains an initial UTF-8 Byte Order Mark (`\xef\xbb\xbf`). Ingestion readers must use `encoding="utf-8-sig"` to prevent `\ufeff` from prepending the first header column.
5. **Historical Baseline & Coverage**: Order purchase timestamps span from **2016-09-04** to **2018-10-17** across 634 unique dates. An uninterrupted, dense period of continuous daily transactions runs from **January 1, 2017 through August 31, 2018**.
6. **KPI Compatibility**: The dataset 100% supports PicketIQ's Phase 3 KPI definitions (`daily_revenue`, `order_count`, `average_order_value`, `cancellation_rate`, `delivery_delay_rate`) and Phase 4 rolling Z-score baseline anomaly detection.

---

## File Inventory

| File Name | Exists | File Size (Bytes) | File Size (MB) | Format / Delimiter | Encoding | Parse Status |
|---|---|---|---|---|---|---|
| `olist_customers_dataset.csv` | Yes | 9,033,957 | 8.62 MB | CSV, comma (`,`) | UTF-8 | Valid (100%) |
| `olist_orders_dataset.csv` | Yes | 17,654,914 | 16.84 MB | CSV, comma (`,`) | UTF-8 | Valid (100%) |
| `olist_order_items_dataset.csv` | Yes | 15,438,671 | 14.72 MB | CSV, comma (`,`) | UTF-8 | Valid (100%) |
| `olist_order_payments_dataset.csv` | Yes | 5,777,138 | 5.51 MB | CSV, comma (`,`) | UTF-8 | Valid (100%) |
| `olist_products_dataset.csv` | Yes | 2,379,446 | 2.27 MB | CSV, comma (`,`) | UTF-8 | Valid (100%) |
| `olist_sellers_dataset.csv` | Yes | 174,703 | 0.17 MB | CSV, comma (`,`) | UTF-8 | Valid (100%) |
| `product_category_name_translation.csv` | Yes | 2,613 | 0.003 MB | CSV, comma (`,`) | UTF-8 (with BOM) | Valid (100% with `utf-8-sig`) |
| **Total** | **7 / 7** | **50,457,442** | **48.13 MB** | — | — | **451,535 rows parsed** |

---

## Schema Findings

| Table / File | Detected Columns | Row Count | PicketIQ Required Columns Present | Unexpected / Extra Columns | Duplicate Headers |
|---|---|---|---|---|---|
| `olist_customers_dataset.csv` | `customer_id`, `customer_unique_id`, `customer_zip_code_prefix`, `customer_city`, `customer_state` | 99,441 | Yes (5/5) | None | None |
| `olist_sellers_dataset.csv` | `seller_id`, `seller_zip_code_prefix`, `seller_city`, `seller_state` | 3,095 | Yes (4/4) | None | None |
| `olist_products_dataset.csv` | `product_id`, `product_category_name`, `product_name_lenght`, `product_description_lenght`, `product_photos_qty`, `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm` | 32,951 | Yes (6/6) | `product_name_lenght`, `product_description_lenght`, `product_photos_qty` | None |
| `product_category_name_translation.csv` | `product_category_name`, `product_category_name_english` | 71 | Yes (2/2) | None | None |
| `olist_orders_dataset.csv` | `order_id`, `customer_id`, `order_status`, `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date` | 99,441 | Yes (8/8) | None | None |
| `olist_order_items_dataset.csv` | `order_id`, `order_item_id`, `product_id`, `seller_id`, `shipping_limit_date`, `price`, `freight_value` | 112,650 | Yes (7/7) | None | None |
| `olist_order_payments_dataset.csv` | `order_id`, `payment_sequential`, `payment_type`, `payment_installments`, `payment_value` | 103,886 | Yes (5/5) | None | None |

*Note on `olist_products_dataset.csv`: The three additional columns (`product_name_lenght`, `product_description_lenght`, `product_photos_qty`) are non-critical catalog metadata and are safely ignored by PicketIQ's schema.*

---

## Missing Values

| File | Column Name | Null / Empty Count | Null % | Missingness Category | Notes / Analysis |
|---|---|---|---|---|---|
| `olist_customers_dataset.csv` | All 5 columns | 0 | 0.00% | None | Complete dataset |
| `olist_sellers_dataset.csv` | All 4 columns | 0 | 0.00% | None | Complete dataset |
| `product_category_name_translation.csv` | All 2 columns | 0 | 0.00% | None | Complete dataset |
| `olist_order_items_dataset.csv` | All 7 columns | 0 | 0.00% | None | Complete dataset |
| `olist_order_payments_dataset.csv` | All 5 columns | 0 | 0.00% | None | Complete dataset |
| `olist_products_dataset.csv` | `product_category_name` | 610 | 1.85% | Expected Nullable | Uncategorized catalog items; schema model supports `nullable=True` |
| `olist_products_dataset.csv` | `product_weight_g` | 2 | 0.006% | Expected Nullable | Minor missing physical dimension |
| `olist_products_dataset.csv` | `product_length_cm` | 2 | 0.006% | Expected Nullable | Minor missing physical dimension |
| `olist_products_dataset.csv` | `product_height_cm` | 2 | 0.006% | Expected Nullable | Minor missing physical dimension |
| `olist_products_dataset.csv` | `product_width_cm` | 2 | 0.006% | Expected Nullable | Minor missing physical dimension |
| `olist_orders_dataset.csv` | `order_approved_at` | 160 | 0.16% | Expected Nullable | Unapproved or canceled before payment |
| `olist_orders_dataset.csv` | `order_delivered_carrier_date` | 1,783 | 1.79% | Expected Nullable | Orders undelivered or canceled before dispatch |
| `olist_orders_dataset.csv` | `order_delivered_customer_date` | 2,965 | 2.98% | Expected Nullable | Canceled, processing, shipped, or in-transit orders |

---

## Duplicate Findings

| Dataset | Candidate Key / Column | Duplicate Key Count | Distinct Keys | Status |
|---|---|---|---|---|
| `customers` | `customer_id` (PK) | 0 | 99,441 | Perfectly unique |
| `customers` | `customer_unique_id` | 3,345 multi-orders | 96,096 | Expected: represents returning buyers |
| `sellers` | `seller_id` (PK) | 0 | 3,095 | Perfectly unique |
| `products` | `product_id` (PK) | 0 | 32,951 | Perfectly unique |
| `orders` | `order_id` (PK) | 0 | 99,441 | Perfectly unique |
| `order_items` | `(order_id, order_item_id)` (PK) | 0 | 112,650 | Perfectly unique composite key |
| `order_payments` | `(order_id, payment_sequential)` (PK) | 0 | 103,886 | Perfectly unique composite key |
| `category_translations` | `product_category_name` (PK) | 0 | 71 | Perfectly unique |
| **All Datasets** | **Full Row Exact Duplicates** | **0** | **451,535** | **Zero exact row duplicates** |

---

## Relational Integrity

| Relationship Description | Source Column | Target Table & Column | Orphan Records | Orphan % | Integrity Status |
|---|---|---|---|---|---|
| Orders -> Customer | `orders.customer_id` | `customers.customer_id` | 0 | 0.00% | **100.0% Valid** |
| Items -> Order | `order_items.order_id` | `orders.order_id` | 0 | 0.00% | **100.0% Valid** |
| Items -> Product | `order_items.product_id` | `products.product_id` | 0 | 0.00% | **100.0% Valid** |
| Items -> Seller | `order_items.seller_id` | `sellers.seller_id` | 0 | 0.00% | **100.0% Valid** |
| Payments -> Order | `order_payments.order_id` | `orders.order_id` | 0 | 0.00% | **100.0% Valid** |
| Products -> Translation | `products.product_category_name` | `translation.product_category_name` | 13 products | 0.04% | **99.96% Valid** |

### Category Translation Discrepancy Detail
The translation lookup file contains 71 English mappings. Products contain 73 unique non-null Portuguese categories. Exactly 2 categories lack translations in `product_category_name_translation.csv`:
1. `portateis_cozinha_e_preparadores_de_alimentos` (portable kitchen / food preparers)
2. `pc_gamer` (gaming PC)

Together, these two untranslated categories represent only **13 products** out of 32,951 items. In relational joins, outer joins safely handle these without data loss.

---

## Date/Time Quality

### Timestamp Range & Span
- **Earliest Order Purchase**: `2016-09-04 21:15:19`
- **Latest Order Purchase**: `2018-10-17 17:30:18`
- **Calendar Span**: 774 calendar days
- **Active Calendar Dates**: 634 dates
- **Inactive Dates**: 140 dates
  - *Context*: Olist ran early pilot transactions in September and October 2016 (approximately 329 orders), with negligible activity in November/December 2016. Sustained, continuous daily commercial operations began on **January 1, 2017** and ran uninterrupted through **August 31, 2018** (October 2018 has 4 closing administrative orders).

### Chronological Validation
- **Unparseable / Corrupted Timestamps**: **0** (All dates adhere to standard `YYYY-MM-DD HH:MM:SS` format).
- **Approved Before Purchase**: **0** records.
- **Delivered Customer Before Purchase**: **0** records.
- **Carrier Dispatch Before Purchase**: **166** records (0.17%). A small timing discrepancy between seller log updates and order creation.
- **Delivered Customer Before Carrier Dispatch**: **23** records (0.02%). Small edge-case logging inversion.
- **Delivered After Estimated Date (Delayed)**: **7,827 delivered orders** (8.11%). This validates the business utility of PicketIQ's `delivery_delay_rate` KPI.

---

## Financial Sanity

| Financial Field | Min Value | Max Value | Mean Value | Median Value | Zero Count | Negative Count | Unparseable Count |
|---|---|---|---|---|---|---|---|
| `order_items.price` | R$ 0.85 | R$ 6,735.00 | R$ 120.65 | R$ 74.99 | 0 | 0 | 0 |
| `order_items.freight_value` | R$ 0.00 | R$ 409.68 | R$ 19.99 | R$ 16.26 | 383 (free shipping) | 0 | 0 |
| `order_payments.payment_value` | R$ 0.00 | R$ 13,664.08 | R$ 154.10 | R$ 100.00 | 9 (voucher discounts) | 0 | 0 |
| `order_payments.payment_installments` | 0 | 24 | 2.85 | 1 | 2 (zero-installment edge case) | 0 | 0 |

### Extreme Values Analysis
- Highest item price: R$ 6,735.00 (`product_id = '480dd3feb9e83d4f42182fc164fd275b'`, small agriculture equipment).
- Highest single payment: R$ 13,664.08 (order containing 8 items of high-value computer accessories).
- Zero payment values: Exactly 9 payment records have `payment_value = 0.00`. All 9 use payment type `voucher`, indicating full voucher offset.
- Zero price values: Exactly 0. Every item has a strictly positive price.

---

## Order Statuses

| Order Status | Order Count | Percentage | Customer Delivery Date Present | Missing Customer Delivery Date |
|---|---|---|---|---|
| `delivered` | 96,478 | 97.02% | 96,470 | 8 |
| `shipped` | 1,107 | 1.11% | 0 | 1,107 |
| `canceled` | 625 | 0.63% | 6 (post-delivery cancel) | 619 |
| `unavailable` | 609 | 0.61% | 0 | 609 |
| `invoiced` | 314 | 0.32% | 0 | 314 |
| `processing` | 301 | 0.30% | 0 | 301 |
| `created` | 5 | 0.005% | 0 | 5 |
| `approved` | 2 | 0.002% | 0 | 2 |
| **Total** | **99,441** | **100.0%** | **96,476** | **2,965** |

### Status Audit Observations
- 97.02% of all orders reach `delivered` status.
- `canceled` and `unavailable` orders account for 1.24% (1,234 orders combined).
- Only 8 `delivered` orders lack a delivery timestamp (0.008%), which PicketIQ's delivery delay filter automatically excludes from the denominator.

---

## Order / Item / Payment Consistency

1. **Orders Without Items**: Exactly **775 orders** (0.78%) have no associated line items in `olist_order_items_dataset.csv`.
   - *Status Breakdown*: 603 `unavailable`, 164 `canceled`, 5 `created`, 2 `invoiced`, 1 `shipped`.
   - *Conclusion*: These represent unfilled or cancelled orders where no merchandise was dispatched. PicketIQ's `daily_revenue` already explicitly excludes `canceled` and `unavailable` orders.
2. **Orders Without Payments**: Exactly **1 order** (`order_id = 'bfbd0f9bdef84302105ad712db648a6c'`, status `delivered`) has no record in `olist_order_payments_dataset.csv`.
3. **Multi-Item Orders**: **9,803 orders** (9.86%) contain multiple items (maximum 21 items in an order).
4. **Multi-Payment Orders**: **2,961 orders** (2.98%) split payments across multiple tenders (e.g. combination of voucher + credit card, or split credit cards).
5. **Item + Freight Total vs Payment Value**:
   - For orders with items and payments, **98,089 orders** (99.4%) have `sum(price) + sum(freight) == sum(payment_value)` matching to within 1 cent.
   - **303 orders** exhibit discrepancies > R$ 0.01 (mean discrepancy R$ 10.79), typical of marketplace promotions, system rounding, or post-purchase credit adjustments.

---

## Data Coverage

| Dimension | Measured Real Count |
|---|---|
| Total Orders | 99,441 |
| Total Customers (Transactions) | 99,441 |
| Unique Customers (Individuals) | 96,096 |
| Total Registered Sellers | 3,095 |
| Total Catalog Products | 32,951 |
| Total Order Line Items | 112,650 |
| Total Payment Transactions | 103,886 |
| Earliest Purchase Date | 2016-09-04 |
| Latest Purchase Date | 2018-10-17 |
| Dense Continuous Operational Period | **2017-01-01 to 2018-08-31** (608 consecutive days) |
| Total Distinct Purchase Dates | 634 |

---

## KPI Compatibility

| Metric Name | Phase 3 Repository Definition | Supported by Real Data? | Relevant Source Columns | Real-Data Caveats Discovered |
|---|---|---|---|---|
| **`daily_revenue`** | `sum(order_items.price)` on purchase date, excluding `canceled` and `unavailable` orders. | **Fully Supported** | `order_items.price`, `orders.order_status`, `orders.order_purchase_timestamp` | Excludes freight and payment installments correctly. 775 orders have no items, but 767 of them are canceled/unavailable anyway. |
| **`order_count`** | `count(distinct orders.order_id)` on purchase date across all statuses. | **Fully Supported** | `orders.order_id`, `orders.order_purchase_timestamp` | Captures all 99,441 orders placed by calendar date. |
| **`average_order_value`** | `daily_revenue / count(revenue_eligible_orders)`. | **Fully Supported** | `orders.order_id`, `orders.order_status`, `order_items.price` | Correctly handles single and multi-item orders. Avoids division by zero during early pilot dates. |
| **`cancellation_rate`** | `count(canceled_orders) / total_orders`. | **Fully Supported** | `orders.order_status`, `orders.order_purchase_timestamp` | 625 canceled orders distributed across the timeline provide realistic baseline variance. |
| **`delivery_delay_rate`** | `count(delayed) / count(delivered_with_valid_dates)`. | **Fully Supported** | `orders.order_delivered_customer_date`, `orders.order_estimated_delivery_date` | 7,827 delayed deliveries (8.11% overall). Zero-denominator rule handles pilot dates and in-transit orders gracefully. |

---

## Risks / Caveats

1. **UTF-8 Byte Order Mark in Category Translations**:
   - `product_category_name_translation.csv` begins with `\xef\xbb\xbf`.
   - *Action required*: Standard Python `open(..., encoding="utf-8-sig")` must be used during ingestion so that `product_category_name` is recognized without a leading `\ufeff`.
2. **Missing Category Translations**:
   - 2 categories (`portateis_cozinha_e_preparadores_de_alimentos` and `pc_gamer`) covering 13 products do not exist in `product_category_name_translation.csv`.
   - *Impact*: Low (0.04% of products). Handled safely by nullable foreign keys or outer joins.
3. **Sparse Pilot Dates (Late 2016)**:
   - Between September 2016 and December 2016, orders are sparse (some weeks with 0 orders).
   - *Impact*: PicketIQ's minimum history guard ($N \ge 7$ in Phase 4) automatically skips these early ramp-up dates, preventing false-positive anomaly spikes.
4. **Delivered Orders Missing Actual Delivery Timestamp**:
   - 8 orders with status `delivered` have null `order_delivered_customer_date`.
   - *Impact*: PicketIQ's delay rate definition requires both dates to be non-null, so these 8 orders are correctly excluded from the denominator.

---

## Final Audit Verdict

> **VERDICT: READY FOR INGESTION**  
>
> The raw Olist Brazilian E-Commerce dataset is authentic, structurally sound, and clean. There are zero primary-key collisions, zero orphan transactional records, strictly non-negative pricing, and 100% parseable timestamps. With `encoding="utf-8-sig"` applied to translation loading, the dataset is fully qualified for Phase 2 batch ingestion and Phase 3–4 analytical computation.
