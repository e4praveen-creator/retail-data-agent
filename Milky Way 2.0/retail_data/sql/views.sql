-- Agent-facing views avoid repeated hierarchy joins and expose integer money.
CREATE VIEW v_product AS
SELECT s.*,st.style_code,st.style_name,st.price_tier,st.fit_group,
 b.brand_key,b.brand_name,b.is_private_label,c.color_name,z.size_system,z.size_label,
 ca.category_key,ca.category_name,de.department_key,de.department_name,di.division_key,di.division_name
FROM dim_sku s JOIN dim_style st USING(style_key) JOIN dim_brand b USING(brand_key)
JOIN dim_color c USING(color_key) JOIN dim_size z USING(size_key)
JOIN dim_category ca USING(category_key) JOIN dim_department de USING(department_key)
JOIN dim_division di USING(division_key);

CREATE VIEW v_sales AS
SELECT l.*,d.calendar_date,d.calendar_year,d.calendar_month,d.retail_year,d.retail_week,d.retail_period,
 h.channel_key,h.customer_key,h.loyalty_key,h.selling_store_key,h.market_store_key,h.fulfillment_method_key,
 p.style_key,p.style_name,p.brand_name,p.category_name,p.department_name,p.division_name
FROM fact_sales_line l JOIN fact_transaction h USING(transaction_key)
JOIN dim_date d ON l.date_key=d.date_key JOIN v_product p ON l.sku_key=p.sku_key;

-- Returns are aggregated before joining to prevent future one-to-many fan-out.
CREATE VIEW v_sales_after_returns AS
SELECT s.*,coalesce(r.returned_units,0) returned_units,coalesce(r.refund_net_cents,0) refund_net_cents,
 (s.net_sales_cents-coalesce(r.refund_net_cents,0)) realized_net_sales_cents,
 (s.cost_of_goods_cents-coalesce(r.recovered_cost_cents,0)) net_cost_of_goods_cents,
 (s.net_sales_cents-coalesce(r.refund_net_cents,0)-s.cost_of_goods_cents+coalesce(r.recovered_cost_cents,0)) merchandise_margin_cents
FROM v_sales s LEFT JOIN (SELECT sales_line_key,sum(returned_quantity) returned_units,
 sum(refund_net_cents) refund_net_cents,sum(recovered_cost_cents) recovered_cost_cents
 FROM fact_return_line GROUP BY sales_line_key) r USING(sales_line_key);

-- Calendar-period reporting: returns deducted on return date, not original sale date.
CREATE VIEW v_merchandise_activity AS
SELECT date_key,sku_key,net_sales_cents merchandise_revenue_cents,quantity net_units,'SALE' activity_type FROM fact_sales_line
UNION ALL
SELECT return_date_key,sku_key,-refund_net_cents,-returned_quantity,'RETURN' FROM fact_return_line;
