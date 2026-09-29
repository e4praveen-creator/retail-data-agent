# Install Milky Way 2.0 from Git

[Application README](README.md) · [Developer handbook](retail_app/docs/developer/README.md) · [Release notes](retail_app/docs/developer/RELEASE.md)

The current application release is **2.1.1**. All commands below run from this `Milky Way 2.0` folder. This is the application at port **8766**; the repository's older top-level application is separate.

## Included and locally supplied files

Git contains the complete application source, prebuilt UI and its hashed chunks, domain references, generator/schema, lockfiles, tests and team documentation. Copying `static/app.js` alone is insufficient; retain the whole `retail_app/static/` folder.

Git excludes the generated warehouse, installed dependencies, API credentials, chats, published custom workspace state and logs. A new installation starts with the built-in workspace. Move custom content/history through a verified SQLite backup if needed; never commit the private state database or a full-installation ZIP.

## 1. Install application dependencies

Use Python 3.12:

```sh
python3.12 -m venv .venv-runtime
.venv-runtime/bin/python -m pip install -r retail_app/requirements.lock.txt
```

The included frontend is already built. Node and pnpm are needed only to edit/build/test it.

## 2. Supply or reproduce the synthetic warehouse

To reuse an existing dataset, supply these files together:

- `retail_data/data/full/retail.duckdb`
- `retail_data/data/full/manifest.json`

The source catalog, metric definitions, playbooks and generator references remain in their checked-in locations. Optional Parquet exports are useful for portability and validation; the application queries DuckDB directly.

Alternatively, generate the full fictional dataset in a separate environment pinned to the generator's dependencies:

```sh
python3.12 -m venv retail_data/.venv
retail_data/.venv/bin/python -m pip install -r retail_data/requirements.lock.txt
retail_data/.venv/bin/python retail_data/src/generate.py --output retail_data/data/full --seed 20250925 --headers 5000000 --stores 60 --customers 600000 --memory 3GB --threads 4
retail_data/.venv/bin/python retail_data/src/validate.py --data retail_data/data/full
```

Generation requires substantial local disk/memory and refuses a nonempty output folder. See the [data kit](retail_data/README.md) for resource guidance and regeneration rules. A small sample is useful for experimentation but cannot satisfy the full-dataset regression suite. Reproduction verifies logical data contents; byte-for-byte database hashes can vary across environments.

## 3. Configure reasoning locally

```sh
cp retail_app/.env.example retail_app/.env
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in the ignored file or process environment. Existing process values take precedence. Credentials stay on the server; never commit `.env`. The deterministic playbooks work without model credentials.

## 4. Start and check

```sh
./retail_app/start.sh
```

Open http://127.0.0.1:8766. `/health/ready` checks warehouse and SQLite availability; model configuration presence does not prove provider access. The app creates local state and seeds built-in knowledge/skills/profiles on first start.

For source changes, install the pinned frontend toolchain/dependencies in `retail_app`, then use the [repository maintenance workflow](retail_app/docs/developer/REPOSITORY_MAINTENANCE.md). The offline suite needs the full warehouse; running it makes no live model calls.

## Preserve an existing installation

Before copying state, use:

```sh
.venv-runtime/bin/python -m retail_app.maintenance backup
```

The verified SQLite backup contains chats, memories, custom workspace assets/releases, feedback and evaluations. Follow the [restore procedure](retail_app/docs/developer/RELEASE.md) in a separate state directory with the service stopped for the final switch. Configure secrets separately and recreate dependencies on the new machine.
