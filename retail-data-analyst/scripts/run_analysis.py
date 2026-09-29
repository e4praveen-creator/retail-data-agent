#!/usr/bin/env python3
"""Read-only baseline queries for the Summit Field retail playbooks.

The results are evidence for an analyst, not a generated narrative or causal model.
Run from the project root with the project's pinned duckdb dependency installed.
"""

import argparse
import datetime as dt
import itertools
import json
import os
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

try:
    import duckdb
except ImportError as exc:
    raise SystemExit("duckdb is required; install retail_data/requirements.lock.txt") from exc


DEFAULT_DATA = Path("retail_data/data/full/retail.duckdb")
DEFAULT_START = "2025-01-05"  # Sunday; 51 complete weeks through 2025-12-27.
DEFAULT_END = "2025-12-27"

# Query tuple: (output name, SQL, parameter names). Every SQL statement is SELECT-only.
REPORTS = {
    "trend": [(
        "weekly_sales",
        """SELECT CASE WHEN d.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END period,
                  CAST(date_trunc('week', d.calendar_date + INTERVAL 1 DAY) - INTERVAL 1 DAY AS DATE) week_start,
                  sum(l.net_sales_cents) sales_before_returns_cents, sum(l.quantity) sold_units,
                  count(DISTINCT l.transaction_key) orders
           FROM fact_sales_line l JOIN dim_date d USING(date_key)
           WHERE d.calendar_date BETWEEN ? AND ? OR d.calendar_date BETWEEN ? AND ?
           GROUP BY 1,2 ORDER BY 2,1""",
        ("start", "end", "compare_start", "compare_end", "start", "end")),
    ],
    "pvm": [(
        "sku_channel_periods",
        """SELECT CASE WHEN s.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END period,
                  s.sku_key,s.channel_key,sum(s.quantity) units,sum(s.net_sales_cents) sales_cents
           FROM v_sales s
           WHERE s.calendar_date BETWEEN ? AND ? OR s.calendar_date BETWEEN ? AND ?
           GROUP BY 1,2,3 ORDER BY 2,3,1""",
        ("start", "end", "compare_start", "compare_end", "start", "end")),
    ],
    "growth": [(
        "division_contributions",
        """SELECT s.division_name,
                  sum(CASE WHEN s.calendar_date BETWEEN ? AND ? THEN s.net_sales_cents ELSE 0 END) current_sales_cents,
                  sum(CASE WHEN s.calendar_date BETWEEN ? AND ? THEN s.net_sales_cents ELSE 0 END) comparison_sales_cents,
                  sum(CASE WHEN s.calendar_date BETWEEN ? AND ? THEN s.net_sales_cents ELSE -s.net_sales_cents END) change_cents
           FROM v_sales s
           WHERE s.calendar_date BETWEEN ? AND ? OR s.calendar_date BETWEEN ? AND ?
           GROUP BY 1 ORDER BY abs(change_cents) DESC""",
        ("start", "end", "compare_start", "compare_end", "start", "end", "start", "end", "compare_start", "compare_end")),
    ],
    "margin": [(
        "division_margin_components",
        """SELECT CASE WHEN s.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END period,
                  s.division_name,sum(s.net_sales_cents) original_net_sales_cents,
                  sum(s.refund_net_cents) returned_revenue_cents,
                  sum(s.cost_of_goods_cents) original_cogs_cents,
                  sum(s.cost_of_goods_cents-s.net_cost_of_goods_cents) recovered_cost_cents,
                  sum(s.realized_net_sales_cents) realized_sales_cents,
                  sum(s.merchandise_margin_cents) merchandise_margin_cents
           FROM v_sales_after_returns s
           WHERE s.calendar_date BETWEEN ? AND ? OR s.calendar_date BETWEEN ? AND ?
           GROUP BY 1,2 ORDER BY 2,1""",
        ("start", "end", "compare_start", "compare_end", "start", "end")),
    ],
    "seasonality": [(
        "retail_week_pattern",
        """SELECT d.retail_year,d.retail_week,min(d.calendar_date) first_date,max(d.calendar_date) last_date,
                  count(DISTINCT d.calendar_date) days_with_sales,
                  sum(l.quantity) units,sum(l.net_sales_cents) sales_before_returns_cents
           FROM fact_sales_line l JOIN dim_date d USING(date_key)
           WHERE d.calendar_date BETWEEN ? AND ? OR d.calendar_date BETWEEN ? AND ?
           GROUP BY 1,2 ORDER BY 1,2""",
        ("start", "end", "compare_start", "compare_end")),
    ],
    "scorecard": [(
        "division_scorecard",
        """SELECT CASE WHEN s.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END period,
                  s.division_name,sum(s.realized_net_sales_cents) realized_sales_cents,
                  sum(s.quantity) sold_units,sum(s.merchandise_margin_cents) merchandise_margin_cents,
                  sum(s.returned_units) returned_units,count(DISTINCT s.transaction_key) orders,
                  count(DISTINCT CASE WHEN s.customer_key>0 THEN s.customer_key END) identified_buyers
           FROM v_sales_after_returns s
           WHERE s.calendar_date BETWEEN ? AND ? OR s.calendar_date BETWEEN ? AND ?
           GROUP BY 1,2 ORDER BY 2,1""",
        ("start", "end", "compare_start", "compare_end", "start", "end")),
    ],
    "channels": [(
        "channel_orders",
        """SELECT CASE WHEN d.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END period,
                  c.channel_name,count(*) orders,sum(h.units) sold_units,
                  sum(h.net_sales_cents) sales_before_returns_cents,
                  CAST(sum(h.net_sales_cents) AS DOUBLE)/nullif(count(*),0) aov_before_returns_cents
           FROM fact_transaction h JOIN dim_date d USING(date_key) JOIN dim_channel c USING(channel_key)
           WHERE d.calendar_date BETWEEN ? AND ? OR d.calendar_date BETWEEN ? AND ?
           GROUP BY 1,2 ORDER BY 2,1""",
        ("start", "end", "compare_start", "compare_end", "start", "end")),
        (
        "pos_store_orders",
        """SELECT st.store_name,st.region,count(*) orders,sum(h.net_sales_cents) sales_before_returns_cents,
                  CAST(sum(h.net_sales_cents) AS DOUBLE)/nullif(count(*),0) aov_before_returns_cents
           FROM fact_transaction h JOIN dim_date d USING(date_key)
           JOIN dim_store st ON h.selling_store_key=st.store_key
           WHERE d.calendar_date BETWEEN ? AND ? AND h.selling_store_key>0
           GROUP BY 1,2 ORDER BY sales_before_returns_cents DESC""",
        ("start", "end")),
    ],
    "concentration": [(
        "style_pareto",
        """WITH x AS (SELECT s.style_name,sum(s.net_sales_cents) sales_cents
                     FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1)
           SELECT style_name,sales_cents,
                  sum(sales_cents) OVER (ORDER BY sales_cents DESC,style_name) cumulative_sales_cents,
                  sum(sales_cents) OVER () total_sales_cents
           FROM x ORDER BY sales_cents DESC,style_name""",
        ("start", "end")),
    ],
    "pricing": [(
        "division_price_realization",
        """SELECT s.division_name,sum(s.quantity) units,
                  sum(s.gross_sales_cents) effective_regular_sales_cents,
                  sum(s.markdown_cents) markdown_cents,
                  sum(s.promotion_discount_cents) promotion_discount_cents,
                  sum(s.net_sales_cents) realized_sales_cents,
                  CAST(sum(s.net_sales_cents) AS DOUBLE)/nullif(sum(s.quantity),0) realized_price_cents_per_unit
           FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ?
           GROUP BY 1 ORDER BY realized_sales_cents DESC""",
        ("start", "end")),
        (
        "selling_price_buckets",
        """SELECT s.division_name,CAST(floor(s.selling_unit_price_cents/1000.0)*10 AS INTEGER) usd_bucket_start,
                  sum(s.quantity) units,sum(s.net_sales_cents) realized_sales_cents
           FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ?
           GROUP BY 1,2 ORDER BY 1,2""",
        ("start", "end")),
    ],
    "promotions": [(
        "campaign_associated_sales",
        """SELECT p.promotion_key,p.promotion_name,p.valid_from,p.valid_to,p.discount_pct,p.loyalty_only,
                  count(*) redeemed_lines,sum(s.quantity) redeemed_units,
                  sum(s.net_sales_cents) associated_sales_before_returns_cents,
                  sum(s.promotion_discount_cents) promotion_discount_cents,
                  sum(s.merchandise_margin_cents) associated_cohort_merchandise_margin_cents
           FROM v_sales_after_returns s JOIN dim_promotion p USING(promotion_key)
           WHERE s.calendar_date BETWEEN ? AND ? AND s.promotion_key>0
           GROUP BY 1,2,3,4,5,6 ORDER BY associated_sales_before_returns_cents DESC""",
        ("start", "end")),
    ],
    "cohorts": [(
        "first_observed_purchase_cohorts",
        """WITH orders AS (
              SELECT h.customer_key,d.calendar_date sale_date,h.net_sales_cents
              FROM fact_transaction h JOIN dim_date d USING(date_key)
              WHERE h.customer_key>0 AND d.calendar_date<=?),
           firsts AS (SELECT customer_key,min(sale_date) first_date FROM orders GROUP BY 1),
           per_customer AS (
              SELECT f.customer_key,f.first_date,
                     count(*) FILTER (WHERE o.sale_date>f.first_date AND o.sale_date<=f.first_date+INTERVAL 90 DAY) repeat_90_orders,
                     count(*) FILTER (WHERE o.sale_date>f.first_date AND o.sale_date<=f.first_date+INTERVAL 180 DAY) repeat_180_orders
              FROM firsts f JOIN orders o USING(customer_key) GROUP BY 1,2)
           SELECT CAST(date_trunc('month',first_date) AS DATE) cohort_month,count(*) identified_buyers,
                  count(*) FILTER (WHERE first_date<=?-INTERVAL 90 DAY) eligible_90,
                  count(*) FILTER (WHERE first_date<=?-INTERVAL 90 DAY AND repeat_90_orders>0) repeat_buyers_90,
                  count(*) FILTER (WHERE first_date<=?-INTERVAL 180 DAY) eligible_180,
                  count(*) FILTER (WHERE first_date<=?-INTERVAL 180 DAY AND repeat_180_orders>0) repeat_buyers_180
           FROM per_customer WHERE first_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""",
        ("end", "end", "end", "end", "end", "start", "end")),
    ],
    "lapse": [(
        "recency_distribution",
        """WITH customer_history AS (
              SELECT h.customer_key,max(d.calendar_date) last_date,count(*) orders,
                     sum(h.net_sales_cents) historical_sales_cents
              FROM fact_transaction h JOIN dim_date d USING(date_key)
              WHERE h.customer_key>0 AND d.calendar_date<=? GROUP BY 1)
           SELECT CASE WHEN date_diff('day',last_date,?)<=30 THEN '00-30 days'
                       WHEN date_diff('day',last_date,?)<=90 THEN '31-90 days'
                       WHEN date_diff('day',last_date,?)<=180 THEN '91-180 days'
                       ELSE '181+ days' END recency_band,
                  count(*) identified_buyers,sum(orders) historical_orders,
                  sum(historical_sales_cents) historical_sales_cents
           FROM customer_history GROUP BY 1 ORDER BY 1""",
        ("end", "end", "end", "end")),
    ],
    "segments": [(
        "behavior_groups",
        """WITH c AS (SELECT h.customer_key,max(d.calendar_date) last_date,count(*) orders,
                           sum(h.net_sales_cents) sales_cents,sum(h.promotion_discount_cents) promo_discount_cents
                    FROM fact_transaction h JOIN dim_date d USING(date_key)
                    WHERE h.customer_key>0 AND d.calendar_date BETWEEN ? AND ? GROUP BY 1),
           labeled AS (SELECT *,CASE WHEN orders>=3 AND date_diff('day',last_date,?)<=90 THEN 'active frequent'
                                   WHEN orders>=3 THEN 'frequent lapsed'
                                   WHEN date_diff('day',last_date,?)<=90 THEN 'active occasional'
                                   ELSE 'occasional lapsed' END segment FROM c)
           SELECT segment,count(*) identified_buyers,sum(orders) orders,sum(sales_cents) sales_cents,
                  sum(promo_discount_cents) promotion_discount_cents
           FROM labeled GROUP BY 1 ORDER BY sales_cents DESC""",
        ("start", "end", "end", "end")),
    ],
    "affinity": [(
        "category_pairs",
        """WITH basket AS (SELECT DISTINCT s.transaction_key,s.category_name
                           FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ?),
           n AS (SELECT count(DISTINCT transaction_key) total_baskets FROM basket),
           singles AS (SELECT category_name,count(*) baskets FROM basket GROUP BY 1),
           pairs AS (SELECT a.category_name category_a,b.category_name category_b,count(*) joint_baskets
                     FROM basket a JOIN basket b ON a.transaction_key=b.transaction_key
                      AND a.category_name<b.category_name GROUP BY 1,2)
           SELECT p.category_a,p.category_b,p.joint_baskets,a.baskets baskets_a,b.baskets baskets_b,n.total_baskets,
                  CAST(p.joint_baskets AS DOUBLE)*n.total_baskets/nullif(a.baskets*b.baskets,0) lift
           FROM pairs p JOIN singles a ON p.category_a=a.category_name
           JOIN singles b ON p.category_b=b.category_name CROSS JOIN n
           ORDER BY p.joint_baskets DESC""",
        ("start", "end")),
    ],
    "loyalty": [(
        "loyalty_attachment",
        """SELECT CASE WHEN h.loyalty_key>0 THEN 'attached' ELSE 'not attached' END loyalty_usage,
                  count(*) orders,sum(h.net_sales_cents) sales_before_returns_cents,
                  sum(h.units) sold_units,count(DISTINCT CASE WHEN h.customer_key>0 THEN h.customer_key END) identified_buyers,
                  CAST(sum(h.net_sales_cents) AS DOUBLE)/nullif(count(*),0) aov_before_returns_cents
           FROM fact_transaction h JOIN dim_date d USING(date_key)
           WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""",
        ("start", "end")),
    ],
    "returns": [(
        "division_channel_return_cohorts",
        """SELECT s.division_name,c.channel_name,sum(s.quantity) original_units,
                  sum(s.returned_units) returned_units,sum(s.net_sales_cents) original_sales_cents,
                  sum(s.refund_net_cents) refund_merchandise_cents
           FROM v_sales_after_returns s JOIN dim_channel c USING(channel_key)
           WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1,2 ORDER BY returned_units DESC""",
        ("start", "end")),
        (
        "return_reasons",
        """SELECT rr.return_reason,count(*) return_lines,sum(r.refund_net_cents) refund_merchandise_cents
           FROM fact_return_line r JOIN dim_return_reason rr USING(return_reason_key)
           JOIN dim_date d ON r.return_date_key=d.date_key
           WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1 ORDER BY return_lines DESC""",
        ("start", "end")),
    ],
    "velocity": [(
        "slow_stocked_skus",
        """WITH sold AS (SELECT s.sku_key,sum(s.quantity) sold_units,sum(s.net_sales_cents) sales_cents
                        FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1),
           latest AS (SELECT max(i.week_end_date_key) week_end_date_key FROM fact_inventory_weekly i
                      JOIN dim_date d ON i.week_end_date_key=d.date_key WHERE d.calendar_date<=?),
           stock AS (SELECT i.sku_key,sum(i.available_units) available_units
                     FROM fact_inventory_weekly i JOIN latest x USING(week_end_date_key) GROUP BY 1)
           SELECT p.division_name,p.style_name,p.sku_code,s.sold_units,s.sales_cents,st.available_units
           FROM stock st LEFT JOIN sold s USING(sku_key) JOIN v_product p USING(sku_key)
           ORDER BY st.available_units DESC,coalesce(s.sold_units,0) ASC""",
        ("start", "end", "end")),
    ],
    "inventory": [(
        "latest_inventory_by_division",
        """WITH latest AS (SELECT max(i.week_end_date_key) week_end_date_key FROM fact_inventory_weekly i
                      JOIN dim_date d ON i.week_end_date_key=d.date_key WHERE d.calendar_date<=?)
           SELECT i.week_end_date_key,p.division_name,sum(i.opening_on_hand_units) opening_units,
                  sum(i.receipt_units) receipt_units,sum(i.restocked_units) restocked_units,
                  sum(i.sold_units) sold_units,sum(i.shrink_units) shrink_units,
                  sum(i.closing_on_hand_units) closing_units,sum(i.available_units) available_units,
                  sum(i.reserved_units) reserved_units
           FROM fact_inventory_weekly i JOIN latest x USING(week_end_date_key)
           JOIN v_product p USING(sku_key) GROUP BY 1,2 ORDER BY closing_units DESC""",
        ("end",)),
    ],
    "fulfillment": [(
        "method_orders_and_returns",
        """WITH heads AS (
              SELECT h.fulfillment_method_key,count(*) orders,sum(h.net_sales_cents) original_sales_cents,
                     sum(h.units) sold_units
              FROM fact_transaction h JOIN dim_date d USING(date_key)
              WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1),
           lines AS (
              SELECT s.fulfillment_method_key,sum(s.returned_units) returned_units,
                     sum(s.merchandise_margin_cents) merchandise_margin_cents
              FROM v_sales_after_returns s WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1)
           SELECT f.fulfillment_method,h.orders,h.original_sales_cents,h.sold_units,
                  l.returned_units,l.merchandise_margin_cents
           FROM heads h JOIN lines l USING(fulfillment_method_key)
           JOIN dim_fulfillment_method f USING(fulfillment_method_key)
           ORDER BY h.orders DESC""",
        ("start", "end", "start", "end")),
    ],
}


def decimal(value):
    return Decimal(int(value))


def shapley_pvm(rows):
    """Exact three-factor Q × share × price split for continuing SKU/channel cells."""
    periods = {}
    for row in rows:
        periods.setdefault((row["sku_key"], row["channel_key"]), {})[row["period"]] = row
    matched = []
    entry_exit = Decimal(0)
    prior_total = Decimal(0)
    current_total = Decimal(0)
    for pair in periods.values():
        old, new = pair.get("comparison"), pair.get("current")
        prior_total += decimal(old["sales_cents"]) if old else 0
        current_total += decimal(new["sales_cents"]) if new else 0
        if old and new and old["units"] and new["units"]:
            matched.append((decimal(old["units"]), decimal(new["units"]),
                            decimal(old["sales_cents"])/decimal(old["units"]),
                            decimal(new["sales_cents"])/decimal(new["units"])))
        else:
            entry_exit += (decimal(new["sales_cents"]) if new else 0) - (decimal(old["sales_cents"]) if old else 0)
    q0 = sum((x[0] for x in matched), Decimal(0))
    q1 = sum((x[1] for x in matched), Decimal(0))
    effects = {"volume_cents": Decimal(0), "mix_cents": Decimal(0), "realized_rate_cents": Decimal(0)}
    if q0 and q1:
        def value(factors):
            q = q1 if "volume" in factors else q0
            return q * sum(((x[1]/q1 if "mix" in factors else x[0]/q0) *
                            (x[3] if "realized_rate" in factors else x[2]) for x in matched), Decimal(0))
        for perm in itertools.permutations(("volume", "mix", "realized_rate")):
            state = set()
            before = value(state)
            for factor in perm:
                state.add(factor)
                after = value(state)
                effects[factor + "_cents"] += (after-before)/Decimal(6)
                before = after
    effects["entry_exit_cents"] = entry_exit
    rounded = {key:int(value.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)) for key,value in effects.items()}
    rounded["comparison_sales_cents"] = int(prior_total)
    rounded["current_sales_cents"] = int(current_total)
    rounded["change_cents"] = int(current_total-prior_total)
    rounded["rounding_adjustment_cents"] = rounded["change_cents"]-sum(rounded[k] for k in
        ("volume_cents","mix_cents","realized_rate_cents","entry_exit_cents"))
    rounded["reconciles"] = (sum(rounded[k] for k in
        ("volume_cents","mix_cents","realized_rate_cents","entry_exit_cents","rounding_adjustment_cents"))
        == rounded["change_cents"])
    return [rounded]


def fetch(con, sql, values):
    cursor = con.execute(sql, values)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def run_one(con, slug, dates, limit):
    outputs = []
    for name, sql, parameters in REPORTS[slug]:
        values = [dates[p] for p in parameters]
        rows = fetch(con, sql, values)
        if slug == "pvm":
            rows = shapley_pvm(rows)
        total_rows = len(rows)
        outputs.append({"name": name, "rows": rows[:limit], "row_count": total_rows,
                        "truncated": total_rows > limit, "sql": sql.strip(),
                        "parameters": [str(v) for v in values]})
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List playbook slugs")
    parser.add_argument("--playbook", choices=sorted(REPORTS)+["all"])
    parser.add_argument("--data", type=Path, default=Path(os.getenv("RETAIL_DB", DEFAULT_DATA)))
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--compare-start")
    parser.add_argument("--compare-end")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--out", type=Path, help="Write the JSON result to this path")
    args = parser.parse_args()
    if args.list:
        print("\n".join(sorted(REPORTS)))
        return 0
    if not args.playbook:
        parser.error("--playbook is required unless --list is used")
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    compare_start = dt.date.fromisoformat(args.compare_start) if args.compare_start else start-dt.timedelta(days=364)
    compare_end = dt.date.fromisoformat(args.compare_end) if args.compare_end else end-dt.timedelta(days=364)
    if start > end or compare_start > compare_end:
        parser.error("Each period start must be on or before its end")
    if (end-start) != (compare_end-compare_start):
        parser.error("Current and comparison periods must contain the same number of days")
    if start < dt.date(2024,1,1) or end > dt.date(2025,12,31):
        parser.error("Sales analysis dates must lie within 2024-01-01..2025-12-31")
    if compare_start < dt.date(2024,1,1) or compare_end > dt.date(2025,12,31):
        parser.error("Comparison dates must lie within 2024-01-01..2025-12-31")
    if compare_end >= start:
        parser.error("Comparison period must end before the current period begins")
    if args.limit < 1:
        parser.error("--limit must be positive")
    if not args.data.is_file():
        parser.error("DuckDB file not found: " + str(args.data))
    dates = {"start":start,"end":end,"compare_start":compare_start,"compare_end":compare_end}
    slugs = sorted(REPORTS) if args.playbook == "all" else [args.playbook]
    result = {"dataset":"synthetic Summit Field", "database":str(args.data.resolve()),
              "period":{k:str(v) for k,v in dates.items()},
              "basis":"sale date; original merchandise sales before returns unless a column says otherwise",
              "results":{}, "warnings":[
                  "Descriptive analysis only; promotion, loyalty, channel and price differences are not causal.",
                  "Customer history is left-censored at 2024-01-01; sales stop at 2025-12-31."]}
    with duckdb.connect(str(args.data), read_only=True) as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='2GB'")
        for slug in slugs:
            result["results"][slug] = run_one(con, slug, dates, args.limit)
    output = json.dumps(result, indent=2, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
