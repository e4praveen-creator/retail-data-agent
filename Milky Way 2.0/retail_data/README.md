# Summit Field — synthetic retail data starter kit

A fully fictional omnichannel sporting-goods/apparel retailer, designed for a local Retail Data Agent. **No real customer records, retailer transactions, proprietary schemas, or product catalog were copied.** Public concepts inform the design; every number and business rule is an invented simulation assumption.

Start with the generated `data/full/retail.duckdb` file. It contains the complete dataset and convenient analytical views. Parquet copies are in `data/full/parquet/`. You do not need to regenerate the data to explore it.

## What you get

| Component | Default scope |
|---|---|
| Completed transaction headers | Exactly 5,000,000 |
| Sales lines | About 11 million; 1–5 lines per transaction |
| Sales dates | January 1, 2024–December 31, 2025 |
| Return observation window | Through March 1, 2026, allowing every sale a full 60 days |
| Stores / distribution centers | 60 fictional stores / 2 DCs |
| Merchandise | 6 divisions, 12 departments, 24 categories, 120 styles, 2,400 SKUs |
| Brands | 12 fictional brands, including one private label |
| Customers / loyalty | 600,000 identified customers plus anonymous key 0; 480,000 loyalty accounts plus no-loyalty key 0 |
| Pricing | 57,600 SKU/channel/quarter price records |
| Promotions | 144 division/month campaigns plus no-promotion key 0 |
| Inventory | Weekly balances for every SKU/location, including zero-sale weeks |
| Deliverables | DuckDB, partitioned Parquet, schema DDL, field dictionary, catalog JSON, manifest, validation report, example queries |
| Integration starter | Local FastAPI reports and a small LangGraph workflow; no API key needed |

Exact generated counts are in `data/full/manifest.json`. The kit is a data foundation and a tested integration example, not a complete conversational analyst.

## Open the documentation first

- [Delivery and verification report](docs/DELIVERY_REPORT.md): actual row counts, sizes, checks, and test limitations.
- [Model and business rules](docs/MODEL.md): table grains, join paths, retail assumptions, and limitations.
- [Metric contract](docs/METRICS.md): precise definitions to give your agent.
- [Public inspiration](docs/SOURCES.md): public references and what was borrowed conceptually.
- [Data dictionary](docs/DATA_DICTIONARY.md): every field, type, meaning, and relationship. A copy is also inside each generated dataset.
- [Schema DDL](sql/schema.sql): executable empty-table DDL with primary/foreign keys. A copy is also inside each generated dataset.
- `data/full/metadata/catalog.json`: schema context your agent can read.
- [Example SQL](sql/example_queries.sql): ten retail questions with queries.
- [Example rows](docs/SAMPLE_ROWS.json): the first three records from every full-dataset table.

A **dimension** describes something, such as a product or customer. A **fact** records something that happened or a measured balance. A **key** links the same thing across tables. **Grain** means exactly what one row represents. **Parquet** is compact column-based storage; **DuckDB** is the local engine that queries it. A **container** bundles the code and dependencies so the same commands run on different computers.

## Easiest container setup

Install Docker Desktop if it is not already installed. Open a terminal **inside this `retail_data` folder**. Reserve roughly 10 GB of free disk space and 4–6 GB of Docker memory as starting allowances. Actual observed size/time are recorded in the delivery report; performance depends on your computer.

If the full dataset is already present, skip generation:

```sh
docker compose up --build api
```

Open [the interactive API page](http://localhost:8000/docs). Try `GET /health`, then `GET /reports/{report}` with `division_sales`, `monthly_sales`, or `channel_orders`. The date fields default to the two sales years. Extend `end_date` to `2026-03-01` to include all return-date deductions. Press Ctrl+C to stop.

If you only have the source kit and no generated data:

```sh
docker compose run --build --rm generator
docker compose up --build api
```

For a small first trial instead:

```sh
docker compose run --build --rm generator python src/generate.py --headers 10000 --stores 3 --customers 1000 --output data/sample
```

This creates a separate sample. The API defaults to `data/full`; to serve the sample, change the compose `RETAIL_DATA_DIR` value to `/app/data/sample`.

The generator refuses to overwrite a nonempty output folder. To try a new seed, choose a new folder with `--output`. A failed build keeps its partial files for diagnosis; use another folder when retrying.

## Run with Python instead

Python 3.9+ is supported by this tested starter; the container uses Python 3.11. From this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
```

On Windows, use `py` in place of `python3` to create the environment, then `.venv\Scripts\activate` to activate it. The commands after activation use `python` on either platform.

If you do not already have the dataset:

```sh
python src/generate.py --output data/full
```

To validate or serve the existing data:

```sh
python src/validate.py --data data/full
python src/verify_parquet.py --data data/full
python -m uvicorn api:app --app-dir src --host 127.0.0.1 --port 8000
```

To try LangGraph separately:

```sh
python src/graph_demo.py
```

The graph runs a named division-sales query and returns the result plus its SQL evidence. It is deliberately a small deterministic integration test; it does not call a language model. The same `run_report` function can become a tool in your analyst's reasoning loop.

For custom locations, set `RETAIL_DATA_DIR` before starting the API/graph. Example on macOS/Linux: `export RETAIL_DATA_DIR=data/sample`. In PowerShell: `$env:RETAIL_DATA_DIR="data/sample"`.

## Query the data directly

Create a file named `explore.py` in this folder with:

```python
import duckdb
con = duckdb.connect('data/full/retail.duckdb', read_only=True)
rows = con.execute('''
    SELECT division_name,
           round(sum(net_sales_cents) / 100.0, 2) AS sales_usd
    FROM v_sales
    GROUP BY division_name
    ORDER BY sales_usd DESC
''').fetchall()
for row in rows:
    print(row)
```

Run `python explore.py`. This reports sales **before returns**, tax, and shipping. See the metric contract for other definitions.

Parquet is an equivalent portable export. To query it without the warehouse, connect to an empty in-memory DuckDB database, change the working directory to `data/full`, and execute `metadata/parquet_views.sql`. The file creates views over relative Parquet paths, followed by the analytical views. Partition columns are excluded from the logical schema. For a container/remote path, change the working directory or adapt these paths.

## Reproducibility and tuning

- Default seed: `20250925`. Explicit hashed pseudo-random streams determine each record. No generation-time network calls.
- Default parameters: `--headers 5000000 --stores 60 --customers 600000 --memory 3GB --threads 4`.
- SKU and calendar dimensions stay fixed; the header, store, and customer sizes are configurable. Larger store counts also expand inventory.
- `duckdb==1.4.3` is pinned because DuckDB hash behavior is not promised across releases. `requirements.lock.txt` records the tested complete Python dependency set; `requirements.txt` lists direct dependencies. These versions are a tested baseline, not a claim that they are the newest.
- Same seed, dimensions, code, and DuckDB version reproduce table contents, even if physical row order differs. Changing store/customer counts also changes foreign-key assignment and is a different dataset.
- A manifest records counts, settings, column fingerprints, and SHA-256 hashes of the exported Parquet files. File hashes verify an existing export; byte-for-byte Parquet reproducibility across platforms/thread counts is not promised.
- DuckDB may spill temporary work to the output folder. A memory limit controls the engine's buffer budget, not total process memory. Reduce `--threads` to 2 and increase memory modestly if needed.
- The generated database omits physical constraints for loading speed; the validator enforces the logical key and relationship contract. The exported DDL includes constraints for a fresh constrained copy.
- `tests/test_integration.py` checks schema loading, exact table reproducibility, Parquet round trips, API behavior, query examples, and LangGraph. See its command-line help.

## Important analytical boundaries

Inventory is weekly and replenishment is constructed to fulfill observed demand. There are no simulated lost sales or genuine out-of-stock causal events. Do not use this dataset to claim you have proved stockouts caused a sales decline. Promotions are correlated with price and time; there is no treatment/control experiment. Customer and brand names are invented, and even seemingly realistic rates are **assumptions, not retailer benchmarks**.

The model covers completed merchandise sales and returns. It excludes cancellations, payment authorization, exchanges as linked workflows, gift-card accounting, suppliers/purchase orders, delivery actuals, and historical changes to customer/store attributes. Monetary units are US cents. Tax is a deliberately simplified flat 7%; it is not jurisdictional tax logic.
