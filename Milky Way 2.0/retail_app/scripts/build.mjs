import { buildFrontend } from "./build-frontend.mjs";

const args = process.argv.slice(2);
if (args.length && !(args.length === 2 && args[0] === "--outdir")) {
  throw Error("Usage: node scripts/build.mjs [--outdir directory]");
}
const { manifest } = await buildFrontend(args[1]);
console.log(
  `Frontend built: ${manifest.initial_bytes.toLocaleString("en-US")} initial bytes, ${manifest.total_bytes.toLocaleString("en-US")} total bytes across ${manifest.files.length} files.`,
);
