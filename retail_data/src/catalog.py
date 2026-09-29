"""Logical schema, join contract and machine-readable field definitions."""
TABLES = {}
def add(name, grain, pk, **fk):
    TABLES[name]={'grain':grain,'pk':pk.split(','),'fk':fk}

add('dim_date','One calendar day; Gregorian and Sunday-based 4-5-4 retail attributes.','date_key')
add('dim_time','One minute of a local wall-clock day.','time_key')
add('dim_channel','One ordering channel, plus key 0 for all/not applicable.','channel_key')
add('dim_fulfillment_method','One completed fulfillment method.','fulfillment_method_key')
add('dim_store','One fictional store; key 0 is digital/no selling store.','store_key')
add('dim_location','One stock-holding store or distribution center.','location_key',store_key='dim_store.store_key')
add('dim_division','One merchandise division; key 0 is not applicable.','division_key')
add('dim_department','One department belonging to one division.','department_key',division_key='dim_division.division_key')
add('dim_category','One category belonging to one department.','category_key',department_key='dim_department.department_key')
add('dim_brand','One fictional merchandise brand.','brand_key')
add('dim_color','One color.','color_key')
add('dim_size','One size/configuration within a size system.','size_key')
add('dim_style','One product model; five styles per category.','style_key',category_key='dim_category.category_key',brand_key='dim_brand.brand_key')
add('dim_sku','One sellable style/color/size combination.','sku_key',style_key='dim_style.style_key',color_key='dim_color.color_key',size_key='dim_size.size_key')
add('dim_customer','One synthetic identified customer; key 0 pools anonymous purchases.','customer_key',home_store_key='dim_store.store_key')
add('dim_loyalty','One fictional loyalty account per enrolled customer; key 0 means no loyalty.','loyalty_key',customer_key='dim_customer.customer_key')
add('dim_promotion','One monthly division campaign or no-promotion sentinel. At most one promotion per line. Inclusive validity dates.','promotion_key',division_key='dim_division.division_key',channel_key='dim_channel.channel_key')
add('dim_return_reason','One return reason.','return_reason_key')
add('fact_price_history','One SKU/channel/quarter price interval. Inclusive validity dates; no overlap.','price_key',sku_key='dim_sku.sku_key',channel_key='dim_channel.channel_key')
add('fact_transaction','One completed sales receipt/order header. Not a return or payment record.','transaction_key',date_key='dim_date.date_key',time_key='dim_time.time_key',customer_key='dim_customer.customer_key',loyalty_key='dim_loyalty.loyalty_key',channel_key='dim_channel.channel_key',selling_store_key='dim_store.store_key',market_store_key='dim_store.store_key',fulfillment_method_key='dim_fulfillment_method.fulfillment_method_key')
add('fact_sales_line','One receipt/order line; IDs have intentional gaps. Same SKU can recur on separate lines.','sales_line_key',transaction_key='fact_transaction.transaction_key',date_key='dim_date.date_key',sku_key='dim_sku.sku_key',price_key='fact_price_history.price_key',promotion_key='dim_promotion.promotion_key',fulfillment_location_key='dim_location.location_key')
add('fact_return_line','One partial return of one unit against one original sale line; at most one return per line.','return_line_key',sales_line_key='fact_sales_line.sales_line_key',transaction_key='fact_transaction.transaction_key',sku_key='dim_sku.sku_key',return_date_key='dim_date.date_key',return_reason_key='dim_return_reason.return_reason_key',return_location_key='dim_location.location_key')
add('fact_inventory_weekly','One SKU/location/week balance including weeks with no sales; last week is partial.','inventory_week_index,location_key,sku_key',location_key='dim_location.location_key',sku_key='dim_sku.sku_key',week_start_date_key='dim_date.date_key',week_end_date_key='dim_date.date_key')

MEANINGS = {
'calendar_date':'Actual calendar date; 2024-01-01 through 2026-03-01.',
'day_index':'Zero-based days since 2024-01-01.',
'calendar_year':'Gregorian year.', 'calendar_month':'Gregorian month 1–12.', 'day_of_month':'Gregorian day 1–31.',
'iso_day_of_week':'Monday=1 through Sunday=7.','is_weekend':'True for Saturday and Sunday.',
'retail_year':'Year of the Sunday nearest February 1 that starts this fiscal year; not a retailer-specific calendar.',
'retail_week':'1-based week within retail year; includes week 53 when applicable.',
'retail_period':'4-5-4 period 1–12; an extra week is assigned to period 12.',
'retail_quarter':'Retail quarter 1–4, derived from period.',
'seasonal_event':'Broad synthetic seasonal label, not an official holiday calendar.',
'demand_weight':'Relative sampling weight for sales dates; includes weekends and seasonal peaks.',
'hour_of_day':'Local wall-clock hour 0–23.','minute_of_hour':'Minute 0–59.','daypart':'Morning, Afternoon, or Evening; midnight is Morning.',
'region':'Synthetic store grouping: Northeast, South, Midwest, West; no real address.',
'store_format':'Standard, Experience, or Digital; invented operating formats.',
'opened_date':'Fictional opening date; all stores precede the sales window.',
'selling_area_sqft':'Synthetic selling floor area; zero for digital sentinel.',
'location_type':'STORE or DC. Every location holds stock; digital store 0 does not.',
'is_private_label':'True for the invented Summit Field brand.',
'size_system':'Apparel alpha, Footwear US unisex, or simplified Equipment configuration.',
'size_sort':'Order within size system, 1–5.',
'size_label':'Human-readable size; equipment A–E are abstract configurations, not real specifications.',
'fit_group':'Unisex for apparel/footwear; otherwise Not applicable.',
'price_tier':'Synthetic style positioning: Value, Core, Premium. Descriptive only; does not drive price.',
'msrp_cents':'Static reference MSRP in cents; not the gross sales basis.',
'unit_cost_cents':'Static per-unit acquisition cost in cents; excludes fulfillment expense.',
'currency_code':'USD only. All monetary fields are integer cents.',
'age_band':'Synthetic adult age band; no birthdates or real people.',
'customer_segment':'Synthetic label; not inferred from observed transactions and not a causal driver.',
'registered_date':'Fictional account registration date before sales start; NULL for anonymous.',
'loyalty_tier':'Base, Plus, Elite, or None; static during the simulation.',
'enrollment_date':'Same as fictional registration date; NULL for no-loyalty sentinel.',
'valid_from':'Inclusive first day of validity.', 'valid_to':'Inclusive final day of validity.',
'discount_pct':'Promotion percent off the post-markdown unit price; 0, 10, 20, or 25.',
'loyalty_only':'If true, redemption requires a nonzero loyalty account.',
'regular_unit_price_cents':'Effective regular unit price before markdown and promotion.',
'markdown_pct':'Price-book markdown percent: 10% in Q4; otherwise 0%.',
'line_number':'Position 1–5 within transaction; (transaction_key,line_number) is unique.',
'quantity':'Sold units on this line, 1 or 2.',
'selling_unit_price_cents':'Actual unit price excluding tax, after markdown and one promotion.',
'gross_sales_cents':'Quantity × effective regular price, before markdown and promotion, excluding tax/shipping.',
'markdown_cents':'Quantity × rounded unit price-book markdown.',
'promotion_discount_cents':'Quantity × rounded promotion discount on the post-markdown unit price.',
'net_sales_cents':'Gross minus markdown minus promotion; before returns, tax and shipping.',
'cost_of_goods_cents':'Sold units × static acquisition cost, before any returned-cost recovery.',
'tax_cents':'Units × rounded selling-unit price × 7%; simplified synthetic tax, not legal tax modeling.',
'promised_delivery_date':'Order date for carry-out/pickup; 2–6 days after order for shipping; promise only.',
'line_count':'Number of lines on header; not unit count.',
'units':'Sum of sold quantities across header lines.',
'shipping_cents':'599 cents for shipped orders below 7500 cents merchandise; otherwise zero; not refunded.',
'total_paid_cents':'Net merchandise sales + tax + shipping on original completed transaction.',
 'transaction_local_timestamp':'Timezone-naive wall-clock date/time; digital uses a nominal common business clock. Not UTC.',
 'transaction_status':'Always COMPLETED; canceled orders and pending authorizations are outside this dataset.',
 'returned_quantity':'Always one; supports partial returns where original quantity is two.',
 'is_restockable':'False for Damaged; all other reasons return stock to the receiving location.',
 'refund_net_cents':'One original discounted selling unit price; positive return deduction.',
 'refund_tax_cents':'Original per-unit tax refunded; positive cents.',
 'refund_total_cents':'Refund merchandise + tax; shipping is not refunded.',
 'recovered_cost_cents':'Original unit cost for restockable returns; zero for damaged returns.',
 'inventory_week_index':'Zero-based 7-day buckets beginning Monday 2024-01-01; separate from retail week.',
 'opening_on_hand_units':'Physical stock at start of week; equals prior closing stock for same SKU/location.',
 'receipt_units':'Synthetic replenishment received during week, including enough to cover sold units; not purchase orders.',
 'sold_units':'Units fulfilled from this SKU/location during week, reconciled to sales lines on order date.',
 'restocked_units':'Restockable returned units received here during week, reconciled to return facts.',
 'shrink_units':'Small synthetic stock loss; separate from non-restockable returned goods.',
 'closing_on_hand_units':'Opening + receipts + restocked returns − sold units − shrink. Do not sum across time.',
 'reserved_units':'Illustrative end-of-week reservations; between zero and closing on-hand; no order-level reservation ledger.',
 'available_units':'Closing on-hand minus reserved; do not sum across time.',
 'in_transit_units':'Illustrative inbound stock at period end; not included in on-hand and no purchase-order linkage.',
}

def describe_column(table, col):
    fk=TABLES[table].get('fk',{}).get(col)
    if fk:
        extra={'date_key':'Sales/order date.', 'selling_store_key':'0 for online orders; actual store for POS.', 'market_store_key':'Customer home market or guest-selected store; not necessarily fulfillment.', 'fulfillment_location_key':'Physical source of stock; shipping is deducted on order date.', 'return_location_key':'Location receiving the return, potentially different from sale fulfillment.', 'home_store_key':'Synthetic home market; zero only for anonymous.', 'channel_key':'Ordering channel; promotion key 0 channel means all.', 'loyalty_key':'0 means no loyalty; otherwise must belong to header customer.', 'customer_key':'0 means anonymous pooled purchases.'}.get(col,'')
        return f'Foreign key → `{fk}`. {extra}'.strip()
    if col in MEANINGS:
        return MEANINGS[col]
    if col in TABLES[table]['pk']:
        return 'Unique synthetic identifier; see table grain. Key 0 is a sentinel where documented.'
    if col.endswith(('_name','_code','_id')):
        return 'Synthetic human-readable '+col.replace('_',' ')+'. No proprietary or personal source data.'
    if col in ('fulfillment_method','return_reason'):
        return 'Descriptive label for the corresponding dimension member.'
    raise KeyError(f'Missing definition: {table}.{col}')
