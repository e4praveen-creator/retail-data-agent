-- DuckDB physical schema. Foreign keys are validated in the generated warehouse.
-- Execute in a fresh database; load referenced dimensions before facts.

CREATE TABLE dim_date (
  date_key INTEGER NOT NULL,
  calendar_date DATE NOT NULL,
  day_index INTEGER NOT NULL,
  calendar_year INTEGER NOT NULL,
  calendar_month INTEGER NOT NULL,
  day_of_month INTEGER NOT NULL,
  iso_day_of_week INTEGER NOT NULL,
  is_weekend BOOLEAN NOT NULL,
  retail_year INTEGER NOT NULL,
  retail_week INTEGER NOT NULL,
  retail_period INTEGER NOT NULL,
  retail_quarter INTEGER NOT NULL,
  seasonal_event VARCHAR NOT NULL,
  demand_weight INTEGER NOT NULL,
  PRIMARY KEY (date_key)
);

CREATE TABLE dim_time (
  time_key INTEGER NOT NULL,
  hour_of_day INTEGER NOT NULL,
  minute_of_hour INTEGER NOT NULL,
  daypart VARCHAR NOT NULL,
  PRIMARY KEY (time_key)
);

CREATE TABLE dim_channel (
  channel_key INTEGER NOT NULL,
  channel_name VARCHAR NOT NULL,
  PRIMARY KEY (channel_key)
);

CREATE TABLE dim_fulfillment_method (
  fulfillment_method_key INTEGER NOT NULL,
  fulfillment_method VARCHAR NOT NULL,
  PRIMARY KEY (fulfillment_method_key)
);

CREATE TABLE dim_store (
  store_key INTEGER NOT NULL,
  store_name VARCHAR NOT NULL,
  region VARCHAR NOT NULL,
  store_format VARCHAR NOT NULL,
  opened_date DATE NOT NULL,
  selling_area_sqft BIGINT NOT NULL,
  PRIMARY KEY (store_key)
);

CREATE TABLE dim_location (
  location_key INTEGER NOT NULL,
  store_key INTEGER NOT NULL,
  location_name VARCHAR NOT NULL,
  location_type VARCHAR NOT NULL,
  PRIMARY KEY (location_key),
  FOREIGN KEY (store_key) REFERENCES dim_store(store_key)
);

CREATE TABLE dim_division (
  division_key INTEGER NOT NULL,
  division_name VARCHAR NOT NULL,
  PRIMARY KEY (division_key)
);

CREATE TABLE dim_department (
  department_key INTEGER NOT NULL,
  division_key INTEGER NOT NULL,
  department_name VARCHAR NOT NULL,
  PRIMARY KEY (department_key),
  FOREIGN KEY (division_key) REFERENCES dim_division(division_key)
);

CREATE TABLE dim_category (
  category_key INTEGER NOT NULL,
  department_key INTEGER NOT NULL,
  category_name VARCHAR NOT NULL,
  PRIMARY KEY (category_key),
  FOREIGN KEY (department_key) REFERENCES dim_department(department_key)
);

CREATE TABLE dim_brand (
  brand_key INTEGER NOT NULL,
  brand_name VARCHAR NOT NULL,
  is_private_label BOOLEAN NOT NULL,
  PRIMARY KEY (brand_key)
);

CREATE TABLE dim_color (
  color_key INTEGER NOT NULL,
  color_name VARCHAR NOT NULL,
  PRIMARY KEY (color_key)
);

CREATE TABLE dim_size (
  size_key INTEGER NOT NULL,
  size_system VARCHAR NOT NULL,
  size_label VARCHAR NOT NULL,
  size_sort INTEGER NOT NULL,
  PRIMARY KEY (size_key)
);

CREATE TABLE dim_style (
  style_key INTEGER NOT NULL,
  category_key INTEGER NOT NULL,
  brand_key INTEGER NOT NULL,
  style_code VARCHAR NOT NULL,
  style_name VARCHAR NOT NULL,
  fit_group VARCHAR NOT NULL,
  price_tier VARCHAR NOT NULL,
  PRIMARY KEY (style_key),
  FOREIGN KEY (category_key) REFERENCES dim_category(category_key),
  FOREIGN KEY (brand_key) REFERENCES dim_brand(brand_key)
);

CREATE TABLE dim_sku (
  sku_key INTEGER NOT NULL,
  sku_code VARCHAR NOT NULL,
  style_key INTEGER NOT NULL,
  color_key INTEGER NOT NULL,
  size_key INTEGER NOT NULL,
  msrp_cents BIGINT NOT NULL,
  unit_cost_cents BIGINT NOT NULL,
  currency_code VARCHAR NOT NULL,
  PRIMARY KEY (sku_key),
  FOREIGN KEY (style_key) REFERENCES dim_style(style_key),
  FOREIGN KEY (color_key) REFERENCES dim_color(color_key),
  FOREIGN KEY (size_key) REFERENCES dim_size(size_key)
);

CREATE TABLE dim_customer (
  customer_key INTEGER NOT NULL,
  customer_id VARCHAR NOT NULL,
  home_store_key INTEGER NOT NULL,
  age_band VARCHAR NOT NULL,
  customer_segment VARCHAR NOT NULL,
  registered_date DATE,
  PRIMARY KEY (customer_key),
  FOREIGN KEY (home_store_key) REFERENCES dim_store(store_key)
);

CREATE TABLE dim_loyalty (
  loyalty_key INTEGER NOT NULL,
  customer_key INTEGER NOT NULL,
  loyalty_id VARCHAR NOT NULL,
  loyalty_tier VARCHAR NOT NULL,
  enrollment_date DATE,
  PRIMARY KEY (loyalty_key),
  FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key)
);

CREATE TABLE dim_promotion (
  promotion_key INTEGER NOT NULL,
  promotion_name VARCHAR NOT NULL,
  division_key INTEGER NOT NULL,
  channel_key INTEGER NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NOT NULL,
  discount_pct INTEGER NOT NULL,
  loyalty_only BOOLEAN NOT NULL,
  PRIMARY KEY (promotion_key),
  FOREIGN KEY (division_key) REFERENCES dim_division(division_key),
  FOREIGN KEY (channel_key) REFERENCES dim_channel(channel_key)
);

CREATE TABLE dim_return_reason (
  return_reason_key INTEGER NOT NULL,
  return_reason VARCHAR NOT NULL,
  PRIMARY KEY (return_reason_key)
);

CREATE TABLE fact_price_history (
  price_key INTEGER NOT NULL,
  sku_key INTEGER NOT NULL,
  channel_key INTEGER NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NOT NULL,
  regular_unit_price_cents BIGINT NOT NULL,
  markdown_pct INTEGER NOT NULL,
  PRIMARY KEY (price_key),
  FOREIGN KEY (sku_key) REFERENCES dim_sku(sku_key),
  FOREIGN KEY (channel_key) REFERENCES dim_channel(channel_key)
);

CREATE TABLE fact_transaction (
  transaction_key BIGINT NOT NULL,
  transaction_id VARCHAR NOT NULL,
  date_key INTEGER NOT NULL,
  time_key INTEGER NOT NULL,
  customer_key INTEGER NOT NULL,
  loyalty_key INTEGER NOT NULL,
  channel_key INTEGER NOT NULL,
  selling_store_key INTEGER NOT NULL,
  market_store_key INTEGER NOT NULL,
  fulfillment_method_key INTEGER NOT NULL,
  transaction_local_timestamp TIMESTAMP NOT NULL,
  line_count INTEGER NOT NULL,
  units INTEGER NOT NULL,
  gross_sales_cents BIGINT NOT NULL,
  markdown_cents BIGINT NOT NULL,
  promotion_discount_cents BIGINT NOT NULL,
  net_sales_cents BIGINT NOT NULL,
  tax_cents BIGINT NOT NULL,
  cost_of_goods_cents BIGINT NOT NULL,
  shipping_cents BIGINT NOT NULL,
  total_paid_cents BIGINT NOT NULL,
  transaction_status VARCHAR NOT NULL,
  currency_code VARCHAR NOT NULL,
  PRIMARY KEY (transaction_key),
  FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY (time_key) REFERENCES dim_time(time_key),
  FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
  FOREIGN KEY (loyalty_key) REFERENCES dim_loyalty(loyalty_key),
  FOREIGN KEY (channel_key) REFERENCES dim_channel(channel_key),
  FOREIGN KEY (selling_store_key) REFERENCES dim_store(store_key),
  FOREIGN KEY (market_store_key) REFERENCES dim_store(store_key),
  FOREIGN KEY (fulfillment_method_key) REFERENCES dim_fulfillment_method(fulfillment_method_key)
);

CREATE TABLE fact_sales_line (
  sales_line_key BIGINT NOT NULL,
  transaction_key BIGINT NOT NULL,
  line_number INTEGER NOT NULL,
  date_key INTEGER NOT NULL,
  sku_key INTEGER NOT NULL,
  price_key INTEGER NOT NULL,
  promotion_key INTEGER NOT NULL,
  fulfillment_location_key INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  regular_unit_price_cents BIGINT NOT NULL,
  selling_unit_price_cents BIGINT NOT NULL,
  unit_cost_cents BIGINT NOT NULL,
  gross_sales_cents BIGINT NOT NULL,
  markdown_cents BIGINT NOT NULL,
  promotion_discount_cents BIGINT NOT NULL,
  net_sales_cents BIGINT NOT NULL,
  tax_cents BIGINT NOT NULL,
  cost_of_goods_cents BIGINT NOT NULL,
  promised_delivery_date DATE NOT NULL,
  PRIMARY KEY (sales_line_key),
  FOREIGN KEY (transaction_key) REFERENCES fact_transaction(transaction_key),
  FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY (sku_key) REFERENCES dim_sku(sku_key),
  FOREIGN KEY (price_key) REFERENCES fact_price_history(price_key),
  FOREIGN KEY (promotion_key) REFERENCES dim_promotion(promotion_key),
  FOREIGN KEY (fulfillment_location_key) REFERENCES dim_location(location_key)
);

CREATE TABLE fact_return_line (
  return_line_key BIGINT NOT NULL,
  sales_line_key BIGINT NOT NULL,
  transaction_key BIGINT NOT NULL,
  sku_key INTEGER NOT NULL,
  return_date_key INTEGER NOT NULL,
  return_reason_key INTEGER NOT NULL,
  return_location_key INTEGER NOT NULL,
  returned_quantity INTEGER NOT NULL,
  is_restockable BOOLEAN NOT NULL,
  refund_net_cents BIGINT NOT NULL,
  refund_tax_cents BIGINT NOT NULL,
  refund_total_cents BIGINT NOT NULL,
  recovered_cost_cents BIGINT NOT NULL,
  PRIMARY KEY (return_line_key),
  FOREIGN KEY (sales_line_key) REFERENCES fact_sales_line(sales_line_key),
  FOREIGN KEY (transaction_key) REFERENCES fact_transaction(transaction_key),
  FOREIGN KEY (sku_key) REFERENCES dim_sku(sku_key),
  FOREIGN KEY (return_date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY (return_reason_key) REFERENCES dim_return_reason(return_reason_key),
  FOREIGN KEY (return_location_key) REFERENCES dim_location(location_key)
);

CREATE TABLE fact_inventory_weekly (
  inventory_week_index INTEGER NOT NULL,
  location_key INTEGER NOT NULL,
  sku_key INTEGER NOT NULL,
  week_start_date_key INTEGER NOT NULL,
  week_end_date_key INTEGER NOT NULL,
  opening_on_hand_units INTEGER NOT NULL,
  receipt_units INTEGER NOT NULL,
  sold_units INTEGER NOT NULL,
  restocked_units INTEGER NOT NULL,
  shrink_units INTEGER NOT NULL,
  closing_on_hand_units INTEGER NOT NULL,
  reserved_units INTEGER NOT NULL,
  available_units INTEGER NOT NULL,
  in_transit_units INTEGER NOT NULL,
  PRIMARY KEY (inventory_week_index, location_key, sku_key),
  FOREIGN KEY (location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY (sku_key) REFERENCES dim_sku(sku_key),
  FOREIGN KEY (week_start_date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY (week_end_date_key) REFERENCES dim_date(date_key)
);
