# Retail Data Agent — Milky Way 2.0

The current application is **Milky Way 2.0, release 2.1.1**, in the [`Milky Way 2.0/`](Milky%20Way%202.0/) folder. It is a trusted local conversational analyst for the fictional Summit Field retail dataset. The earlier top-level `retail_app/` remains a historical implementation.

## Start with the latest application

- [Install from a Git checkout](Milky%20Way%202.0/INSTALL.md)
- [Application README](Milky%20Way%202.0/README.md)
- [Developer handbook and architecture](Milky%20Way%202.0/retail_app/docs/developer/README.md)
- [User and administrator guide](Milky%20Way%202.0/retail_app/docs/developer/USER_ADMIN_GUIDE.md)
- [Release notes and verified limits](Milky%20Way%202.0/retail_app/docs/developer/RELEASE.md)

From this repository root, after installing the runtime and supplying or generating the warehouse:

```sh
cd "Milky Way 2.0"
./retail_app/start.sh
```

Open http://127.0.0.1:8766. The prebuilt browser application is included.

## Current features

- One Retail Agent with 27 validated tools, measured evidence, charts and persistent conversations/investigations.
- Nineteen retail playbooks and eighteen hypothesis templates over read-only DuckDB.
- Five administration sections for knowledge/ontology, skills, answer design, evaluations, feedback and releases.
- Immutable workspace versions, candidate comparison, reviewed publication/rollback, scope editing and answer provenance.
- A 76-case deterministic evaluation foundation, 317 offline backend tests and six frontend suites.
- Strict tool contracts, separated reference context, bounded execution, safe backups and repository maintenance.

## What Git contains

Application/backend/frontend source, the full prebuilt UI with hashed chunks, domain methods, synthetic-data generator/schema, dependency locks, tests, documentation and public verification receipts are included.

Credentials, personal conversations/workspace state, installed dependencies, logs, generated DuckDB/Parquet and local installation archives are excluded. A fresh checkout needs the setup in [INSTALL.md](Milky%20Way%202.0/INSTALL.md). Recreate Python dependencies on the target machine; configure model access locally. Preserve personal state separately with the SQLite backup utility when moving an existing installation.
