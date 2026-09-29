# Data dictionary

All records are synthetic. Money is integer US cents. Date keys use YYYYMMDD.

## dim_date

One calendar day; Gregorian and Sunday-based 4-5-4 retail attributes.

Primary key: `date_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| date_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| calendar_date | DATE | Actual calendar date; 2024-01-01 through 2026-03-01. |
| day_index | INTEGER | Zero-based days since 2024-01-01. |
| calendar_year | INTEGER | Gregorian year. |
| calendar_month | INTEGER | Gregorian month 1–12. |
| day_of_month | INTEGER | Gregorian day 1–31. |
| iso_day_of_week | INTEGER | Monday=1 through Sunday=7. |
| is_weekend | BOOLEAN | True for Saturday and Sunday. |
| retail_year | INTEGER | Year of the Sunday nearest February 1 that starts this fiscal year; not a retailer-specific calendar. |
| retail_week | INTEGER | 1-based week within retail year; includes week 53 when applicable. |
| retail_period | INTEGER | 4-5-4 period 1–12; an extra week is assigned to period 12. |
| retail_quarter | INTEGER | Retail quarter 1–4, derived from period. |
| seasonal_event | VARCHAR | Broad synthetic seasonal label, not an official holiday calendar. |
| demand_weight | INTEGER | Relative sampling weight for sales dates; includes weekends and seasonal peaks. |

## dim_time

One minute of a local wall-clock day.

Primary key: `time_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| time_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| hour_of_day | INTEGER | Local wall-clock hour 0–23. |
| minute_of_hour | INTEGER | Minute 0–59. |
| daypart | VARCHAR | Morning, Afternoon, or Evening; midnight is Morning. |

## dim_channel

One ordering channel, plus key 0 for all/not applicable.

Primary key: `channel_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| channel_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| channel_name | VARCHAR | Synthetic human-readable channel name. No proprietary or personal source data. |

## dim_fulfillment_method

One completed fulfillment method.

Primary key: `fulfillment_method_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| fulfillment_method_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| fulfillment_method | VARCHAR | Descriptive label for the corresponding dimension member. |

## dim_store

One fictional store; key 0 is digital/no selling store.

Primary key: `store_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| store_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| store_name | VARCHAR | Synthetic human-readable store name. No proprietary or personal source data. |
| region | VARCHAR | Synthetic store grouping: Northeast, South, Midwest, West; no real address. |
| store_format | VARCHAR | Standard, Experience, or Digital; invented operating formats. |
| opened_date | DATE | Fictional opening date; all stores precede the sales window. |
| selling_area_sqft | BIGINT | Synthetic selling floor area; zero for digital sentinel. |

## dim_location

One stock-holding store or distribution center.

Primary key: `location_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| location_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| store_key | INTEGER | Foreign key → `dim_store.store_key`. |
| location_name | VARCHAR | Synthetic human-readable location name. No proprietary or personal source data. |
| location_type | VARCHAR | STORE or DC. Every location holds stock; digital store 0 does not. |

## dim_division

One merchandise division; key 0 is not applicable.

Primary key: `division_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| division_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| division_name | VARCHAR | Synthetic human-readable division name. No proprietary or personal source data. |

## dim_department

One department belonging to one division.

Primary key: `department_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| department_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| division_key | INTEGER | Foreign key → `dim_division.division_key`. |
| department_name | VARCHAR | Synthetic human-readable department name. No proprietary or personal source data. |

## dim_category

One category belonging to one department.

Primary key: `category_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| category_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| department_key | INTEGER | Foreign key → `dim_department.department_key`. |
| category_name | VARCHAR | Synthetic human-readable category name. No proprietary or personal source data. |

## dim_brand

One fictional merchandise brand.

Primary key: `brand_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| brand_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| brand_name | VARCHAR | Synthetic human-readable brand name. No proprietary or personal source data. |
| is_private_label | BOOLEAN | True for the invented Summit Field brand. |

## dim_color

One color.

Primary key: `color_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| color_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| color_name | VARCHAR | Synthetic human-readable color name. No proprietary or personal source data. |

## dim_size

One size/configuration within a size system.

Primary key: `size_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| size_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| size_system | VARCHAR | Apparel alpha, Footwear US unisex, or simplified Equipment configuration. |
| size_label | VARCHAR | Human-readable size; equipment A–E are abstract configurations, not real specifications. |
| size_sort | INTEGER | Order within size system, 1–5. |

## dim_style

One product model; five styles per category.

Primary key: `style_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| style_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| category_key | INTEGER | Foreign key → `dim_category.category_key`. |
| brand_key | INTEGER | Foreign key → `dim_brand.brand_key`. |
| style_code | VARCHAR | Synthetic human-readable style code. No proprietary or personal source data. |
| style_name | VARCHAR | Synthetic human-readable style name. No proprietary or personal source data. |
| fit_group | VARCHAR | Unisex for apparel/footwear; otherwise Not applicable. |
| price_tier | VARCHAR | Synthetic style positioning: Value, Core, Premium. Descriptive only; does not drive price. |

## dim_sku

One sellable style/color/size combination.

Primary key: `sku_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| sku_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| sku_code | VARCHAR | Synthetic human-readable sku code. No proprietary or personal source data. |
| style_key | INTEGER | Foreign key → `dim_style.style_key`. |
| color_key | INTEGER | Foreign key → `dim_color.color_key`. |
| size_key | INTEGER | Foreign key → `dim_size.size_key`. |
| msrp_cents | BIGINT | Static reference MSRP in cents; not the gross sales basis. |
| unit_cost_cents | BIGINT | Static per-unit acquisition cost in cents; excludes fulfillment expense. |
| currency_code | VARCHAR | USD only. All monetary fields are integer cents. |

## dim_customer

One synthetic identified customer; key 0 pools anonymous purchases.

Primary key: `customer_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| customer_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| customer_id | VARCHAR | Synthetic human-readable customer id. No proprietary or personal source data. |
| home_store_key | INTEGER | Foreign key → `dim_store.store_key`. Synthetic home market; zero only for anonymous. |
| age_band | VARCHAR | Synthetic adult age band; no birthdates or real people. |
| customer_segment | VARCHAR | Synthetic label; not inferred from observed transactions and not a causal driver. |
| registered_date | DATE | Fictional account registration date before sales start; NULL for anonymous. |

## dim_loyalty

One fictional loyalty account per enrolled customer; key 0 means no loyalty.

Primary key: `loyalty_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| loyalty_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| customer_key | INTEGER | Foreign key → `dim_customer.customer_key`. 0 means anonymous pooled purchases. |
| loyalty_id | VARCHAR | Synthetic human-readable loyalty id. No proprietary or personal source data. |
| loyalty_tier | VARCHAR | Base, Plus, Elite, or None; static during the simulation. |
| enrollment_date | DATE | Same as fictional registration date; NULL for no-loyalty sentinel. |

## dim_promotion

One monthly division campaign or no-promotion sentinel. At most one promotion per line. Inclusive validity dates.

Primary key: `promotion_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| promotion_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| promotion_name | VARCHAR | Synthetic human-readable promotion name. No proprietary or personal source data. |
| division_key | INTEGER | Foreign key → `dim_division.division_key`. |
| channel_key | INTEGER | Foreign key → `dim_channel.channel_key`. Ordering channel; promotion key 0 channel means all. |
| valid_from | DATE | Inclusive first day of validity. |
| valid_to | DATE | Inclusive final day of validity. |
| discount_pct | INTEGER | Promotion percent off the post-markdown unit price; 0, 10, 20, or 25. |
| loyalty_only | BOOLEAN | If true, redemption requires a nonzero loyalty account. |

## dim_return_reason

One return reason.

Primary key: `return_reason_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| return_reason_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| return_reason | VARCHAR | Descriptive label for the corresponding dimension member. |

## fact_price_history

One SKU/channel/quarter price interval. Inclusive validity dates; no overlap.

Primary key: `price_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| price_key | INTEGER | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| sku_key | INTEGER | Foreign key → `dim_sku.sku_key`. |
| channel_key | INTEGER | Foreign key → `dim_channel.channel_key`. Ordering channel; promotion key 0 channel means all. |
| valid_from | DATE | Inclusive first day of validity. |
| valid_to | DATE | Inclusive final day of validity. |
| regular_unit_price_cents | BIGINT | Effective regular unit price before markdown and promotion. |
| markdown_pct | INTEGER | Price-book markdown percent: 10% in Q4; otherwise 0%. |

## fact_transaction

One completed sales receipt/order header. Not a return or payment record.

Primary key: `transaction_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| transaction_key | BIGINT | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| transaction_id | VARCHAR | Synthetic human-readable transaction id. No proprietary or personal source data. |
| date_key | INTEGER | Foreign key → `dim_date.date_key`. Sales/order date. |
| time_key | INTEGER | Foreign key → `dim_time.time_key`. |
| customer_key | INTEGER | Foreign key → `dim_customer.customer_key`. 0 means anonymous pooled purchases. |
| loyalty_key | INTEGER | Foreign key → `dim_loyalty.loyalty_key`. 0 means no loyalty; otherwise must belong to header customer. |
| channel_key | INTEGER | Foreign key → `dim_channel.channel_key`. Ordering channel; promotion key 0 channel means all. |
| selling_store_key | INTEGER | Foreign key → `dim_store.store_key`. 0 for online orders; actual store for POS. |
| market_store_key | INTEGER | Foreign key → `dim_store.store_key`. Customer home market or guest-selected store; not necessarily fulfillment. |
| fulfillment_method_key | INTEGER | Foreign key → `dim_fulfillment_method.fulfillment_method_key`. |
| transaction_local_timestamp | TIMESTAMP | Timezone-naive wall-clock date/time; digital uses a nominal common business clock. Not UTC. |
| line_count | INTEGER | Number of lines on header; not unit count. |
| units | INTEGER | Sum of sold quantities across header lines. |
| gross_sales_cents | BIGINT | Quantity × effective regular price, before markdown and promotion, excluding tax/shipping. |
| markdown_cents | BIGINT | Quantity × rounded unit price-book markdown. |
| promotion_discount_cents | BIGINT | Quantity × rounded promotion discount on the post-markdown unit price. |
| net_sales_cents | BIGINT | Gross minus markdown minus promotion; before returns, tax and shipping. |
| tax_cents | BIGINT | Units × rounded selling-unit price × 7%; simplified synthetic tax, not legal tax modeling. |
| cost_of_goods_cents | BIGINT | Sold units × static acquisition cost, before any returned-cost recovery. |
| shipping_cents | BIGINT | 599 cents for shipped orders below 7500 cents merchandise; otherwise zero; not refunded. |
| total_paid_cents | BIGINT | Net merchandise sales + tax + shipping on original completed transaction. |
| transaction_status | VARCHAR | Always COMPLETED; canceled orders and pending authorizations are outside this dataset. |
| currency_code | VARCHAR | USD only. All monetary fields are integer cents. |

## fact_sales_line

One receipt/order line; IDs have intentional gaps. Same SKU can recur on separate lines.

Primary key: `sales_line_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| sales_line_key | BIGINT | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| transaction_key | BIGINT | Foreign key → `fact_transaction.transaction_key`. |
| line_number | INTEGER | Position 1–5 within transaction; (transaction_key,line_number) is unique. |
| date_key | INTEGER | Foreign key → `dim_date.date_key`. Sales/order date. |
| sku_key | INTEGER | Foreign key → `dim_sku.sku_key`. |
| price_key | INTEGER | Foreign key → `fact_price_history.price_key`. |
| promotion_key | INTEGER | Foreign key → `dim_promotion.promotion_key`. |
| fulfillment_location_key | INTEGER | Foreign key → `dim_location.location_key`. Physical source of stock; shipping is deducted on order date. |
| quantity | INTEGER | Sold units on this line, 1 or 2. |
| regular_unit_price_cents | BIGINT | Effective regular unit price before markdown and promotion. |
| selling_unit_price_cents | BIGINT | Actual unit price excluding tax, after markdown and one promotion. |
| unit_cost_cents | BIGINT | Static per-unit acquisition cost in cents; excludes fulfillment expense. |
| gross_sales_cents | BIGINT | Quantity × effective regular price, before markdown and promotion, excluding tax/shipping. |
| markdown_cents | BIGINT | Quantity × rounded unit price-book markdown. |
| promotion_discount_cents | BIGINT | Quantity × rounded promotion discount on the post-markdown unit price. |
| net_sales_cents | BIGINT | Gross minus markdown minus promotion; before returns, tax and shipping. |
| tax_cents | BIGINT | Units × rounded selling-unit price × 7%; simplified synthetic tax, not legal tax modeling. |
| cost_of_goods_cents | BIGINT | Sold units × static acquisition cost, before any returned-cost recovery. |
| promised_delivery_date | DATE | Order date for carry-out/pickup; 2–6 days after order for shipping; promise only. |

## fact_return_line

One partial return of one unit against one original sale line; at most one return per line.

Primary key: `return_line_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| return_line_key | BIGINT | Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented. |
| sales_line_key | BIGINT | Foreign key → `fact_sales_line.sales_line_key`. |
| transaction_key | BIGINT | Foreign key → `fact_transaction.transaction_key`. |
| sku_key | INTEGER | Foreign key → `dim_sku.sku_key`. |
| return_date_key | INTEGER | Foreign key → `dim_date.date_key`. |
| return_reason_key | INTEGER | Foreign key → `dim_return_reason.return_reason_key`. |
| return_location_key | INTEGER | Foreign key → `dim_location.location_key`. Location receiving the return, potentially different from sale fulfillment. |
| returned_quantity | INTEGER | Always one; supports partial returns where original quantity is two. |
| is_restockable | BOOLEAN | False for Damaged; all other reasons return stock to the receiving location. |
| refund_net_cents | BIGINT | One original discounted selling unit price; positive return deduction. |
| refund_tax_cents | BIGINT | Original per-unit tax refunded; positive cents. |
| refund_total_cents | BIGINT | Refund merchandise + tax; shipping is not refunded. |
| recovered_cost_cents | BIGINT | Original unit cost for restockable returns; zero for damaged returns. |

## fact_inventory_weekly

One SKU/location/week balance including weeks with no sales; last week is partial.

Primary key: `inventory_week_index, location_key, sku_key`.

| Column | DuckDB type | Meaning / relationship |
|---|---|---|
| inventory_week_index | INTEGER | Zero-based 7-day buckets beginning Monday 2024-01-01; separate from retail week. |
| location_key | INTEGER | Foreign key → `dim_location.location_key`. |
| sku_key | INTEGER | Foreign key → `dim_sku.sku_key`. |
| week_start_date_key | INTEGER | Foreign key → `dim_date.date_key`. |
| week_end_date_key | INTEGER | Foreign key → `dim_date.date_key`. |
| opening_on_hand_units | INTEGER | Physical stock at start of week; equals prior closing stock for same SKU/location. |
| receipt_units | INTEGER | Synthetic replenishment received during week, including enough to cover sold units; not purchase orders. |
| sold_units | INTEGER | Units fulfilled from this SKU/location during week, reconciled to sales lines on order date. |
| restocked_units | INTEGER | Restockable returned units received here during week, reconciled to return facts. |
| shrink_units | INTEGER | Small synthetic stock loss; separate from non-restockable returned goods. |
| closing_on_hand_units | INTEGER | Opening + receipts + restocked returns − sold units − shrink. Do not sum across time. |
| reserved_units | INTEGER | Illustrative end-of-week reservations; between zero and closing on-hand; no order-level reservation ledger. |
| available_units | INTEGER | Closing on-hand minus reserved; do not sum across time. |
| in_transit_units | INTEGER | Illustrative inbound stock at period end; not included in on-hand and no purchase-order linkage. |
