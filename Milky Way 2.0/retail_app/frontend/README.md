# Frontend source map

This is a React application bundled with esbuild. The browser loads local assets;
it does not need a CDN or a second development server. The main application guide
is [the developer handbook](../docs/developer/README.md).

## Where to make changes

| File                                          | Responsibility                                                           |
| --------------------------------------------- | ------------------------------------------------------------------------ |
| `chat.jsx`                                    | Chat navigation, saved conversations, requests, polling and composition. |
| `answer-report.jsx`                           | Standard answer sections and measured output presentation.               |
| `chart-table.jsx`, `playbook-charts.jsx`      | Tables, query charts and the 19 playbook chart designs.                  |
| `evidence.jsx`                                | SQL, evidence inspection and report downloads.                           |
| `answer-controls.jsx`                         | Answer provenance, structured feedback and editable chat scope.          |
| `investigation.jsx`                           | Editable hypotheses and investigation evidence.                          |
| `improve-workspace.jsx`                       | Admin navigation, asset lists and workspace loading.                     |
| `workspace/asset-editor.jsx`                  | Guided knowledge, ontology, skill, profile and example authoring.        |
| `workspace/asset-models.js`                   | New asset defaults and independent draft copies.                         |
| `workspace/evaluations.jsx`                   | Evaluation case editing and result comparisons.                          |
| `workspace/evaluation-workbench.jsx`          | Run selection, budgets, polling and review.                              |
| `workspace/feedback-releases.jsx`             | Feedback review, candidates, publication and rollback.                   |
| `workspace/shared.jsx`, `workspace/values.js` | Shared form controls, labels and input validation.                       |
| `analysis-workspace.jsx`                      | Optional dashboard, history, catalog and reference browser.              |
| `lazy-panel.jsx`                              | On-demand screen loading and recoverable load failures.                  |
| `api.js`                                      | Same-origin API requests and consistent error handling.                  |
| `format.js`                                   | Reused number formatters; money input is integer US cents.               |

`app.jsx` preserves the original public imports used by tests and consumers.
Production chat imports the specific renderer modules directly. Do not import
optional admin screens into shared answer components: doing so makes every chat
download the admin code.

## Build and test

Use the Node and pnpm versions declared in [package.json](../package.json).
From `retail_app/`:

```sh
pnpm install --frozen-lockfile
pnpm test:frontend
pnpm run build
```

Frontend rendering tests need the fixtures produced by the backend suite. From
the enclosing Milky Way folder, first run:

```sh
.venv-runtime/bin/python -m retail_app.tests.run_all
```

[The test runner](../scripts/test-frontend.mjs) lists six focused suites. They cover
rendering, evidence, safe Markdown, the admin workflow's forms and contracts, and
delivery. They do not replace browser interaction tests.

## Delivery contract

[The build library](../scripts/build-frontend.mjs) creates an ES module entry at
`static/app.js`, content-addressed chunks under `static/chunks/`, and
`static/asset-manifest.json`. The manifest records every output's byte count,
SHA-256 digest and whether chat needs it on its first load. `index.html` must load
the entry with `type="module"`.

The Improve and analysis workspaces load when opened. Shared answer controls stay
available in chat. A loading status and a failure screen offer retry, reload and
return to chat. No admin actions run merely because a chunk is downloaded.

Build output is written only after compilation and the dependency checks pass.
Each file is replaced atomically; dependencies are published before the entry.
Previous hashed chunks are retained for browser tabs still using the previous
entry. When distributing a release, copy the complete `static/` directory. Do not
delete old chunks on a live installation while old tabs may still need them.

The delivery suite verifies every dependency is present, all manifest hashes
match, optional screens remain deferred, and startup JavaScript stays below
920,000 uncompressed bytes. It builds in a temporary directory and asserts the
shipped entry is unchanged. Revisit that explicit budget deliberately when
adding dependencies; do not silently remove the gate.

For an isolated build inspection without changing the running application's
assets:

```sh
pnpm run build --outdir tmp/frontend-inspection
```

Styles are in `static/chat.css`, `static/improve.css` and `static/app.css`. Format
changed source files with Prettier. Never edit the generated JavaScript directly.
