import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const audit = spawnSync(
  process.execPath,
  [process.env.npm_execpath, "audit", "--audit-level=low", "--json"],
  { encoding: "utf8", timeout: 120_000, maxBuffer: 4 * 1024 * 1024 },
);
if (audit.error) throw audit.error;

const report = JSON.parse(audit.stdout);
if (!report.vulnerabilities || report.error || ![0, 1].includes(audit.status)) {
  throw new Error("npm audit did not return a valid vulnerability report.");
}

const vulnerabilities = Object.values(report.vulnerabilities);
if (audit.status === 0 && vulnerabilities.length === 0) {
  console.log("npm audit found no vulnerabilities.");
  process.exit(0);
}

const advisory = "https://github.com/advisories/GHSA-fc5q-39xc-vjpf";
const consumers = new Set([
  "picomatch",
  "fdir",
  "tinyglobby",
  "vite",
  "@vitejs/plugin-react",
  "@typescript-eslint/typescript-estree",
  "@typescript-eslint/parser",
  "@typescript-eslint/eslint-plugin",
  "@typescript-eslint/type-utils",
  "@typescript-eslint/utils",
  "typescript-eslint",
]);
const { packages } = JSON.parse(
  readFileSync(new URL("../package-lock.json", import.meta.url), "utf8"),
);
const causes = vulnerabilities.flatMap(({ name, via }) =>
  via.filter((cause) => typeof cause === "object").map((cause) => ({ name, cause })),
);
const picomatch = report.vulnerabilities.picomatch;
const knownToolingAdvisory =
  audit.status === 1 &&
  picomatch?.nodes.length === 1 &&
  picomatch.nodes[0] === "node_modules/picomatch" &&
  packages["node_modules/picomatch"]?.version === "4.0.7" &&
  causes.length === 1 &&
  causes[0].name === "picomatch" &&
  causes[0].cause.url === advisory &&
  vulnerabilities.every(({ name }) => consumers.has(name));

if (!knownToolingAdvisory) {
  console.error(JSON.stringify(report.vulnerabilities, null, 2));
  process.exit(1);
}

console.warn(
  `Known build tooling advisory: picomatch 4.0.7 (${advisory}). See docs/DEVELOPMENT.md.`,
);
