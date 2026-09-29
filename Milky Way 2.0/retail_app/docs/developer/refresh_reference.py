"""Regenerate developer contract snapshots using isolated application state.

Run from Milky Way 2.0: .venv-runtime/bin/python retail_app/docs/developer/refresh_reference.py
No model calls, private-state reads, configuration-value exports or warehouse writes.
"""
from pathlib import Path
import ast
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
DOCS = Path(__file__).resolve().parent
OUT = DOCS / "reference"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n")


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def main():
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with tempfile.TemporaryDirectory(prefix="milky-way-doc-reference-") as state:
        os.environ["RETAIL_STATE_DIR"] = state
        from retail_app.backend import agent, conversation, scope, storage, investigations, workspace_assets, workspace_evaluations
        from retail_app.backend.context import INDEX
        from retail_app.backend.main import app
        tools = agent.TOOLS + conversation.tool_definitions(agent.function, agent.S)
        write_json("tools.json", tools)
        openapi = app.openapi()
        write_json("openapi.json", openapi)
        write_json("scope-capabilities.json", scope.query_capabilities())
        # Inventory contains only the explicitly allowlisted domain references.
        write_json("context-inventory.json", INDEX.documents)
        (OUT / "state-schema.sql").write_text(storage.SCHEMA + "\n" + investigations.SCHEMA + "\n" + workspace_assets.SCHEMA + "\n" + workspace_evaluations._SCHEMA)
        write_json("workspace-capabilities.json", workspace_assets.capabilities())
        write_json("enterprise-suite-summary.json", {"case_count":len(workspace_evaluations.seed_suite()["cases"]), "cases":[{"id":c["id"],"category":c["category"],"contract":c["contract"]["type"]} for c in workspace_evaluations.seed_suite()["cases"]], "review_status":"developer_authored; not a human-reviewed live benchmark"})
        lines = ["# API and tool reference", "", "[Handbook](README.md) · [Low-level design](LOW_LEVEL_DESIGN.md)", "",
                 f"Generated from source baseline `{commit[:12]}` at {stamp}. Regenerate with `refresh_reference.py`.", "",
                 "## API routes", "", "The [OpenAPI snapshot](reference/openapi.json) contains request models, validation constraints and path/query parameters. Many handlers return dynamic dictionaries, so OpenAPI does not fully specify every response. See the low-level design for response shapes and lifecycle rules. Static mounts and framework documentation routes are outside this table.", "",
                 "Writes require `X-Retail-App: local`; the browser adds it through `frontend/api.js`. JSON writes use `Content-Type: application/json`. These headers are not authentication. The routes below are relative to the server root.", "",
                 "| Method | Route | Handler / summary |", "|---|---|---|"]
        routes = 0
        for path, methods in openapi["paths"].items():
            for method, spec in methods.items():
                if method not in {"get", "post", "patch", "delete", "put", "head", "options"}: continue
                routes += 1
                lines.append(f"| {method.upper()} | `{path}` | {cell(spec.get('summary', ''))} |")
        lines += ["", "## Active model tools", "", f"**{len(tools)} declared tools:** {len(agent.TOOLS)} core tools and {len(tools)-len(agent.TOOLS)} conversation tools. `query_scoped_sql` is an internal implementation reached through `execute_sql` and hypothesis testing; it is not a separately declared model tool. Undeclared tools are rejected before dispatch; legacy specialist dispatch is removed.", "",
                  "Source: [agent.py](../../backend/agent.py) and [conversation.py](../../backend/conversation.py). Full machine-readable input contracts: [tools.json](reference/tools.json). Schemas use `strict: true`, require all wire fields and disallow additional properties. Optional values use nullable types; the local boundary accepts omitted optional fields for recorded-call compatibility and removes optional nulls before dispatch. The allowlist and local argument validation run before handlers, which retain domain-specific semantic checks. Do not assume the provider schema validates domain meaning.", ""]
        for tool in tools:
            params = tool["parameters"]
            required = params.get("required", [])
            lines += [f"### `{tool['name']}`", "", tool["description"], ""]
            if not params["properties"]:
                lines += ["No input fields.", ""]
                continue
            lines += ["| Input | Type / allowed values | Required |", "|---|---|---|"]
            for name, spec in params["properties"].items():
                typ = spec.get("type", "object")
                if isinstance(typ, list): typ = " or ".join(typ)
                if typ == "array": typ += " of " + spec.get("items", {}).get("type", "values")
                if spec.get("enum"): typ += "; " + ", ".join(map(str, spec["enum"]))
                if "minimum" in spec: typ += "; minimum " + str(spec["minimum"])
                lines.append(f"| `{name}` | {cell(typ)} | {'yes' if name in required else 'no'} |")
            lines.append("")
        lines += ["## Effects and execution boundaries", "",
                  "Context/metric/memory search and inspection read data. Query, playbook, hypothesis-bank and statistical tools create measured or derived evidence in the answer. `plan_turn`, investigation tools and `remember_preference` can write local SQLite state. Presentation tools validate/render the answer; they do not execute arbitrary browser code. `finish_chat` performs final answer persistence after the graph returns.", "",
                  "JSON-valued strings (`scope_json`, `criterion_json`, `hypotheses_json`) are parsed by the server and checked again. They are not SQL or Python execution channels. Model SQL is accepted only through the bounded query interfaces. Tool failures are returned as correction diagnostics and appear in the trace.", ""]
        (DOCS / "API_AND_TOOLS.md").write_text("\n".join(lines))
        inventory = ["# Backend test inventory", "", "[Testing guide](../TESTING.md)", "", "Collected from Python test methods in source; this is an inventory, not a pass receipt. The executed count may also reflect unittest discovery behavior. Frontend suites are listed in the testing guide.", ""]
        test_count = 0
        for path in sorted((ROOT / "retail_app/tests").glob("test_*.py")):
            inventory += [f"## {path.name}", ""]
            for cls in ast.parse(path.read_text()).body:
                if not isinstance(cls, ast.ClassDef): continue
                methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]
                for method in methods:
                    test_count += 1
                    inventory.append(f"- [{cls.name}.{method.name}](../../../tests/{path.name}#L{method.lineno})")
            inventory.append("")
        (OUT / "TEST_INVENTORY.md").write_text("\n".join(inventory))
        samples = {}
        for channel in ("Web", "Mobile app"):
            selected = scope.normalize_scope({"dates": {"start": "2025-07-01", "end": "2025-07-31", "compare_start": "2024-07-01", "compare_end": "2024-07-31"}, "filters": [{"field": "channel_name", "op": "eq", "values": [channel]}, {"field": "division_name", "op": "eq", "values": ["Footwear"]}]})
            samples[channel] = scope.query_retail(selected, ["sales_cents", "units", "orders"], [], True)
        write_json("answer-example-evidence.json", {"generated_at": stamp, "method": "Direct deterministic scoped queries; no model response generated", "samples": samples})
        source_paths = []
        for pattern in ("retail_app/backend/*.py", "retail_app/scripts/*", "retail_app/maintenance.py", "retail_app/service.py", "retail_app/start.sh", "retail_app/pnpm-lock.yaml", "retail_app/static/chunks/*.js", "retail_app/static/asset-manifest.json", "retail_app/frontend/**/*", "retail_app/tests/test_*", "retail_data/sql/*.sql", "retail_data/src/*.py", "retail_app/package.json", "retail_app/requirements.lock.txt", "retail_app/knowledge/*.json", "retail_app/static/*.css", "retail_app/static/index.html", "retail_app/static/app.js"):
            source_paths.extend(p for p in ROOT.glob(pattern) if p.is_file())
        write_json("source-manifest.json", {"generated_at": stamp, "source_commit": commit, "source_state": "working tree implementation over this commit; hashes identify delivered files", "app_version": openapi["info"]["version"], "tool_count": len(tools), "core_tool_count": len(agent.TOOLS), "conversation_tool_count": len(tools)-len(agent.TOOLS), "api_operation_count": routes, "context_document_count": len(INDEX.documents), "backend_test_method_count": test_count, "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(source_paths))}})
        print(json.dumps({"tools": len(tools), "api_operations": routes, "context_documents": len(INDEX.documents), "test_methods": test_count, "examples": {k:v["rows"] for k,v in samples.items()}}, indent=2))


if __name__ == "__main__":
    main()
