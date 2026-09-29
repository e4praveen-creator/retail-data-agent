import { build } from "esbuild";
import { createHash } from "node:crypto";
import { mkdir, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

async function atomicWrite(file, contents) {
  await mkdir(path.dirname(file), { recursive: true });
  const temporary = `${file}.tmp-${process.pid}`;
  try {
    await writeFile(temporary, contents);
    await rename(temporary, file);
  } finally {
    await rm(temporary, { force: true });
  }
}

export async function buildFrontend(
  outdir = path.join(appDirectory, "static"),
) {
  outdir = path.resolve(outdir);
  const result = await build({
    absWorkingDir: appDirectory,
    entryPoints: { app: "frontend/chat.jsx" },
    bundle: true,
    minify: true,
    format: "esm",
    splitting: true,
    target: ["es2022"],
    chunkNames: "chunks/[name]-[hash]",
    outdir,
    metafile: true,
    write: false,
    logLevel: "warning",
  });
  const outputs = result.metafile.outputs;
  for (const output of Object.values(outputs)) {
    for (const dependency of output.imports) {
      if (dependency.external || !outputs[dependency.path]) {
        throw Error(`Missing locally bundled dependency: ${dependency.path}`);
      }
    }
  }
  const entry = Object.keys(outputs).find(
    (name) => outputs[name].entryPoint === "frontend/chat.jsx",
  );
  if (!entry) throw Error("The chat entry point was not built.");
  const initial = new Set();
  function include(name) {
    if (initial.has(name)) return;
    if (!outputs[name]) throw Error(`Missing bundled dependency: ${name}`);
    initial.add(name);
    for (const dependency of outputs[name].imports) {
      if (!dependency.external && dependency.kind !== "dynamic-import")
        include(dependency.path);
    }
  }
  include(entry);
  // This is a delivery contract: optional admin screens must stay out of chat startup.
  for (const name of initial) {
    for (const source of Object.keys(outputs[name].inputs)) {
      if (
        [
          "frontend/workspace/asset-editor.jsx",
          "frontend/workspace/evaluation-workbench.jsx",
          "frontend/analysis-workspace.jsx",
        ].includes(source)
      ) {
        throw Error(`An optional screen became an eager dependency: ${source}`);
      }
    }
  }
  const files = result.outputFiles
    .map((file) => {
      const name = path.relative(appDirectory, file.path);
      return {
        path: path.relative(outdir, file.path),
        bytes: file.contents.byteLength,
        sha256: createHash("sha256").update(file.contents).digest("hex"),
        initial: initial.has(name),
      };
    })
    .sort((a, b) => a.path.localeCompare(b.path));
  const manifest = {
    entry: "app.js",
    initial_bytes: files
      .filter((file) => file.initial)
      .reduce((sum, file) => sum + file.bytes, 0),
    total_bytes: files.reduce((sum, file) => sum + file.bytes, 0),
    files,
  };
  // Publish dependencies first and the stable entry last. Keep older hashed chunks
  // available for tabs already open on a previous release.
  for (const file of result.outputFiles.filter(
    (file) => path.basename(file.path) !== "app.js",
  )) {
    await atomicWrite(file.path, file.contents);
  }
  const entryFile = result.outputFiles.find(
    (file) => path.basename(file.path) === "app.js",
  );
  await atomicWrite(entryFile.path, entryFile.contents);
  await atomicWrite(
    path.join(outdir, "asset-manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  return { manifest, metafile: result.metafile };
}
