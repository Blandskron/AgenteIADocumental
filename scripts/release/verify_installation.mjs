// A clean local clone and fresh named volumes; never deletes existing volumes.
// Run after verify.mjs, when no other bd-final-check checks are running.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { parseEnv } from "node:util";

if (!process.env.VERIFICATION_ENV_FILE) throw Error("Supply the current synthetic VERIFICATION_ENV_FILE");
const root = process.cwd();
const workspace = fs.mkdtempSync(path.join(os.tmpdir(), "bd-clean-clone-"));
const clone = path.join(workspace, "repository");
const report = { started_utc: new Date().toISOString(), source_commit: "", steps: [], volumes_preserved: true };
function run(label, program, args, options = {}) {
  console.log(`Checking ${label}`);
  const result = spawnSync(program, args, { cwd: options.cwd || root, encoding: "utf8", env: options.env || process.env,
    maxBuffer: 16 * 1024 * 1024, shell: false });
  report.steps.push({ label, exit_code: result.status });
  if (result.status !== 0) throw Error(`${label} failed; ${(result.stderr || "").slice(-3000)}`);
  return result.stdout.trim();
}
const current = ["compose", "--env-file", process.env.VERIFICATION_ENV_FILE, "-p", "bd-final-check", "-f", "docker/docker-compose.yml", "-f", "docker/compose/verification.yml"];
report.source_commit = run("resolve source revision", "git", ["rev-parse", "HEAD"]);
run("clone committed source without personal files", "git", ["clone", "--no-hardlinks", "--no-local", root, clone]);
run("checkout tested revision", "git", ["checkout", "--detach", report.source_commit], { cwd: clone });
if (run("clean clone status", "git", ["status", "--porcelain"], { cwd: clone })) throw Error("Clone is not clean");
const envFile = run("create private synthetic configuration", process.execPath, ["scripts/release/prepare_verification.mjs"], { cwd: clone });
const credentials = parseEnv(fs.readFileSync(envFile, "utf8"));
const isolatedEnv = { ...process.env, ...credentials, VERIFICATION_ENV_FILE: envFile };
const freshVolumes = path.join(workspace, "fresh-volumes.yml");
const suffix = randomUUID().replaceAll("-", "");
fs.writeFileSync(freshVolumes, "volumes:\n" + ["postgres_data", "auth_signing_keys", "auth_verification_keys", "verification_documents"]
  .map(name => `  ${name}:\n    name: bd-final-check-clean-${suffix}-${name}\n`).join(""));
const fresh = ["compose", "--env-file", envFile, "-p", "bd-final-check", "-f", path.join(clone, "docker/docker-compose.yml"),
  "-f", path.join(clone, "docker/compose/verification.yml"), "-f", freshVolumes];
const compose = (label, args) => run(label, "docker", [...fresh, ...args], { env: isolatedEnv });
const probe = `bd-final-check-clean-probe-${suffix}`;
try {
  run("stop only the dedicated synthetic stack", "docker", [...current, "stop"]);
  compose("clean installation and automatic migrations/bootstrap", ["up", "-d", "--build", "--wait", "blandskron-frontend"]);
  compose("real embeddings, search, RAG/PDF and isolation from clean clone", ["run", "--rm", "--no-deps", "export-tests", "python", "/verification/demo_flow.py"]);
  compose("create private lifecycle probe", ["run", "-d", "--no-deps", "--name", probe,
    "-e", `INITIAL_ADMIN_USERNAME=${credentials.INITIAL_ADMIN_USERNAME}`,
    "-e", `INITIAL_ADMIN_PASSWORD=${credentials.INITIAL_ADMIN_PASSWORD}`, "export-tests", "sleep", "1800"]);
  try {
    run("bootstrap login/upload/change password", "docker", ["exec", probe, "python", "/verification/persistence_probe.py", "prepare"]);
    compose("complete stop preserving fresh volumes", ["stop"]);
    compose("restart clean installation", ["up", "-d", "--wait", "blandskron-frontend"]);
    run("verify preserved user, password and document", "docker", ["exec", probe, "python", "/verification/persistence_probe.py", "verify"]);
    compose("second startup of clean installation", ["up", "-d", "--wait", "blandskron-frontend"]);
    run("verify no duplicates and no password reset", "docker", ["exec", probe, "python", "/verification/persistence_probe.py", "verify"]);
  } finally {
    run("clean only owned lifecycle fixtures", "docker", ["exec", probe, "python", "/verification/persistence_probe.py", "cleanup"]);
    run("remove disposable probe container", "docker", ["rm", "-f", probe]);
  }
  run("real browser bootstrap login", process.execPath, ["scripts/release/browser_probe.mjs"], { env: isolatedEnv });
  compose("clean-clone postflight", ["run", "--rm", "--no-deps", "database-schema", "psql", "-h", "postgres", "-U", "postgres",
    "-d", "documents_db", "-v", "ON_ERROR_STOP=1", "-f", "/schema/tests/release_cleanup.sql"]);
  report.result = "passed";
} finally {
  report.finished_utc = new Date().toISOString();
  fs.writeFileSync(path.join(root, "docs/release/INSTALLATION_CHECK.json"), JSON.stringify(report, null, 2) + "\n");
  // Private recovery coordinates, not credentials. No personal data were copied.
  fs.writeFileSync(path.join(workspace, "recovery.json"), JSON.stringify({ clone, envFile, freshVolumes }));
  console.log(`Private recovery coordinates: ${path.join(workspace, "recovery.json")}`);
}
