import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PassThrough } from "node:stream";
import React from "react";
import { renderToPipeableStream, renderToString } from "react-dom/server";
import { buildFrontend } from "../scripts/build-frontend.mjs";
import { fmt } from "../frontend/format.js";
import { validateChatDates } from "../frontend/workspace/values.js";
import {
  LazyPanel,
  PanelLoading,
  PanelLoadError,
} from "../frontend/lazy-panel.jsx";

const outdir = await mkdtemp(path.join(tmpdir(), "milkyway-frontend-"));
const productionEntry = new URL("../static/app.js", import.meta.url);
const productionBefore = await readFile(productionEntry);
try {
  const { manifest, metafile } = await buildFrontend(outdir);
  const actual = JSON.parse(
    await readFile(path.join(outdir, "asset-manifest.json"), "utf8"),
  );
  assert.deepEqual(actual, manifest);
  assert(
    manifest.initial_bytes < manifest.total_bytes,
    "Optional screens must be deferred.",
  );
  assert(
    manifest.initial_bytes < 920_000,
    "Chat startup exceeded its uncompressed JavaScript budget.",
  );
  for (const file of manifest.files) {
    const contents = await readFile(path.join(outdir, file.path));
    assert.equal(contents.byteLength, file.bytes);
    assert.equal(
      createHash("sha256").update(contents).digest("hex"),
      file.sha256,
    );
    if (file.path !== "app.js")
      assert.match(file.path, /^chunks\/[\w-]+-[A-Z0-9]{8}\.js$/);
  }
  const outputs = metafile.outputs;
  for (const output of Object.values(outputs)) {
    for (const dependency of output.imports) {
      assert(
        !dependency.external,
        "Browser dependencies must be included locally.",
      );
      assert(
        outputs[dependency.path],
        `Unpublished dependency: ${dependency.path}`,
      );
    }
  }
  const app = Object.values(outputs).find(
    (output) => output.entryPoint === "frontend/chat.jsx",
  );
  const screens = app.imports.filter(
    (dependency) => dependency.kind === "dynamic-import",
  );
  assert.equal(screens.length, 2);
  assert.deepEqual(
    new Set(screens.map((dependency) => outputs[dependency.path].entryPoint)),
    new Set([
      "frontend/improve-workspace.jsx",
      "frontend/analysis-workspace.jsx",
    ]),
  );
  const index = await readFile(
    new URL("../static/index.html", import.meta.url),
    "utf8",
  );
  const pkg = JSON.parse(
    await readFile(new URL("../package.json", import.meta.url), "utf8"),
  );
  assert.match(index, /<script[^>]*type="module"/);
  assert(index.includes(`/static/app.js?v=${pkg.version}`));
} finally {
  await rm(outdir, { recursive: true, force: true });
}
assert.deepEqual(
  await readFile(productionEntry),
  productionBefore,
  "Temporary builds must not overwrite the shipped entry.",
);
assert.equal(fmt(12345, "money"), "$123");
assert.equal(fmt(12345), "12,345");
assert.equal(fmt(null), "—");
assert.throws(
  () => validateChatDates({ start: "2025-02-30", end: "2025-03-02" }),
  /Choose current/,
);

const loading = renderToString(
  <PanelLoading title="Improve workspace" onBack={() => {}} />,
);
assert(loading.includes('role="status"') && loading.includes("Back to chat"));
const failure = renderToString(
  <PanelLoadError
    title="Improve workspace"
    onRetry={() => {}}
    onBack={() => {}}
  />,
);
for (const label of ['role="alert"', "Try again", "Reload app", "Back to chat"])
  assert(failure.includes(label));

// Streaming SSR waits for the actual async loader and verifies its screen receives props.
const loaded = await new Promise((resolve, reject) => {
  const stream = new PassThrough();
  let html = "";
  stream.on("data", (data) => {
    html += data;
  });
  stream.on("end", () => resolve(html));
  stream.on("error", reject);
  const rendering = renderToPipeableStream(
    <LazyPanel
      title="Example"
      load={async () => ({ default: ({ message }) => <p>{message}</p> })}
      panelProps={{ message: "Optional screen loaded" }}
    />,
    {
      onAllReady() {
        rendering.pipe(stream);
      },
      onError: reject,
    },
  );
});
assert(loaded.includes("Optional screen loaded"));
console.log(
  "Frontend delivery passed: complete chunk graph, content hashes, startup budget, deferred screens, accessible loading/recovery and asynchronous screen rendering.",
);
