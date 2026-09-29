# Delivery and verification report

Generated locally on September 25, 2026, with DuckDB 1.4.3, seed 20250925. All records belong to a fictional retailer.

| Delivered entity | Actual rows |
|---|---:|
| `dim_date` | 791 |
| `dim_time` | 1,440 |
| `dim_channel` | 4 |
| `dim_fulfillment_method` | 4 |
| `dim_store` | 61 |
| `dim_location` | 62 |
| `dim_division` | 7 |
| `dim_department` | 12 |
| `dim_category` | 24 |
| `dim_brand` | 12 |
| `dim_color` | 4 |
| `dim_size` | 15 |
| `dim_style` | 120 |
| `dim_sku` | 2,400 |
| `dim_customer` | 600,001 |
| `dim_loyalty` | 480,001 |
| `dim_promotion` | 145 |
| `dim_return_reason` | 4 |
| `fact_price_history` | 57,600 |
| `fact_transaction` | 5,000,000 |
| `fact_sales_line` | 10,995,475 |
| `fact_return_line` | 790,834 |
| `fact_inventory_weekly` | 16,814,400 |

## Verification

- **105/105 full-dataset validation checks passed**: keys, relationships, dates, prices, promotions, money, header totals, returns and inventory reconciliation.
- **68/68 integration checks passed** on a 10,000-header sample and a separately generated replica, with 4 versus 2 generation threads.
- Exact same-seed table contents match using bidirectional `EXCEPT ALL` on all 23 tables.
- All 23 full-dataset Parquet tables also exactly match the database, checked in monthly batches with bidirectional `EXCEPT ALL`: [full_parquet_report.json](full_parquet_report.json).
- Five full-dataset API endpoint checks passed: [full_api_report.json](full_api_report.json).
- All sample Parquet exports exactly match their database tables.
- Published DDL created a fresh database and loaded all sample tables with primary and foreign key constraints enforced.
- All ten example queries execute. Portable Parquet views work. FastAPI report/catalog/health endpoints and invalid-input handling pass. The LangGraph workflow agrees with its direct data tool.
- Full validation details: [full_validation_report.json](full_validation_report.json). Integration details: [integration_report.json](integration_report.json).
- Docker was unavailable on the authoring machine. The Dockerfile and Compose configuration are provided, but a container build/run was **not verified**. Local application code was tested on Python 3.9; the container targets Python 3.11.

## Files and measured size

- Full warehouse: `data/full/retail.duckdb` — 1,088.2 MB (1,088,172,032 bytes).
- Parquet export: `data/full/parquet/` — 392.5 MB (392,508,477 bytes).
- Reported generation + validation + export time: 13.7 seconds on this host. Final database checkpoint is outside the timer; this is an observation, not a performance promise.
- Full manifest: `data/full/manifest.json`, including file hashes and table fingerprints.
- Small ready-made sample: `data/sample/`.
- Source package: `retail_data_source.zip` in the parent workspace; includes source, instructions, DDL, dictionary, and verification reports, but not generated data or Python dependencies.

## Interpreting the data

Weekly inventory is fully reconciled but intentionally replenished to cover observed sales. No stockout-driven lost demand is modeled. Promotions have no experimental control group. The dataset supports descriptive retail analysis and agent tool testing; it does not establish real retailer benchmarks or causal lift.
