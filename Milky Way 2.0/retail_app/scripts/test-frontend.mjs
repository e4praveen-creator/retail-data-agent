import { build } from "esbuild";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const appDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const suites = [
  "test_frontend",
  "test_playbook_visuals",
  "test_answer_report",
  "test_milkyway_frontend",
  "test_improvement_frontend",
  "test_frontend_delivery",
];

for (const suite of suites) {
  const outfile = path.join(appDirectory, "tmp", `${suite}.mjs`);
  await build({
    absWorkingDir: appDirectory,
    entryPoints: [`tests/${suite}.jsx`],
    bundle: true,
    platform: "node",
    format: "esm",
    packages: "external",
    outfile,
    logLevel: "warning",
  });
  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [outfile], {
      cwd: appDirectory,
      stdio: "inherit",
    });
    child.once("error", reject);
    child.once("exit", (code, signal) =>
      code === 0
        ? resolve()
        : reject(Error(`${suite} failed (${signal || code}).`)),
    );
  });
}
console.log(`${suites.length} frontend suites passed.`);
