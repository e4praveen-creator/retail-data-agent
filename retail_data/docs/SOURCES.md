# Public inspiration and provenance

Public pages reviewed September 25, 2026 (local date). No data was scraped, downloaded, or copied into the dataset from a retailer. The names Summit Field and all product/customer/store identifiers are invented for this simulation and do not assert an affiliation.

| Public source | Concept used | What is synthetic |
|---|---|---|
| [DICK'S Sporting Goods public storefront](https://www.dickssportinggoods.com/) | Broad apparel, footwear, sports, golf, fitness and outdoor assortment; loyalty and pickup concepts | All hierarchy members, IDs, brands, products, prices, customers, volumes and probabilities |
| [Product availability and price](https://www.dickssportinggoods.com/s/product-availability-price) | Prices, promotions and availability can differ by online/store channel | Channel price offsets and all promotional rules |
| [Understanding order status](https://www.dickssportinggoods.com/s/understand-order-status) | Online order and pickup are distinguishable states/concepts | This simplified model stores completed sales only, with method and a delivery promise |
| [NRF 4-5-4 calendar](https://nrf.com/resources/4-5-4-calendar) | Retail week/period reporting alongside ordinary calendar months | Implemented Sunday-nearest-February-1 convention; no claim to match a particular retailer or restated comparator |
| [DuckDB Parquet export](https://duckdb.org/docs/lts/guides/file_formats/parquet_export) and [partitioned writes](https://duckdb.org/docs/stable/data/partitioning/partitioned_writes) | Local columnar exports and partition-aware queries | Warehouse schema and generation logic |
| [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) | A small stateful graph can invoke a deterministic data tool | Included example is a single query node, not a finished reasoning agent |
| [FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/) | Containerized local API | Read-only named reports over this dataset |

No actual company sales, loyalty behavior, return rates, margins, store footprint, or inventory performance should be inferred from this simulation. There are no real names, email addresses, postal addresses, or payment details.
