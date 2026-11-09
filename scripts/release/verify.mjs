// Cross-platform synthetic PostgreSQL/service checks. Never use with a personal project.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";

const prefix = ["compose", "--env-file", ".env.example", "-p", "bd-final-check", "-f", "docker/docker-compose.yml", "-f", "docker/compose/verification.yml"];
const folder = fs.mkdtempSync(path.join(os.tmpdir(), "bd-verification-"));
const destination = "docs/release/VERIFICATION.json";
const report = { cards: ["PLAT-001", "DEMO-001"], started_utc: new Date().toISOString(),
  source_commit: spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).stdout.trim(), steps: [] };
async function check(label, args) {
  const start = Date.now(), log = path.join(folder, `${report.steps.length}.log`);
  const output = fs.openSync(log, "w");
  console.log(`Checking ${label}`);
  const child = spawn("docker", [...prefix, ...args], { stdio: ["ignore", output, output], shell: false });
  const code = await new Promise((resolve, reject) => { child.once("error", reject); child.once("exit", resolve); });
  fs.closeSync(output);
  report.steps.push({ label, exit_code: code, seconds: Math.round((Date.now()-start)/1000) });
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.writeFileSync(destination, JSON.stringify(report, null, 2) + "\n");
  if (code !== 0) throw Error(`${label} failed; private log ${log}\n${fs.readFileSync(log, "utf8").slice(-6000)}`);
  console.log(`Passed ${label} (${report.steps.at(-1).seconds}s)`);
}
const sql = (db, script) => ["run", "--rm", "--no-deps", "database-schema", "psql", "-h", "postgres", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-q", "-f", `/schema/${script}`];
await check("Compose", ["config", "--quiet"]);
await check("tenant preflight with active constraints", sql("documents_db", "tests/tenant_preflight.sql"));
for (const script of ["auth/verify_roles.sql", "conversation/verify_role.sql", "rag-chat/verify_role.sql", "embedding/verify_role.sql",
  "search/verify_role.sql", "access/verify_role.sql", "library/verify_role.sql", "transfer/verify_role.sql", "profile/verify_role.sql", "export/verify_role.sql", "drive/verify_role.sql"]) {
  await check(script, sql("documents_db", script));
}
await check("Auth regression", ["exec", "-T", "-e", "POSTGRES_USER=postgres", "-e", "POSTGRES_PASSWORD=admin1234", "auth-service", "python", "manage.py", "test", "users", "core", "--noinput"]);
for (const service of ["conversation-tests", "rag-chat-tests", "embedding-tests", "search-tests", "access-tests", "library-tests", "transfer-tests", "profile-tests", "export-tests", "drive-tests"]) {
  await check(service, ["run", "--build", "--rm", "--no-deps", service]);
  await check(`${service} Ruff`, ["run", "--rm", "--no-deps", service, "ruff", "check", "--no-cache", "app", "tests"]);
}
await check("end-to-end synthetic demo", ["run", "--rm", "--no-deps", "export-tests", "python", "/verification/demo_flow.py"]);
report.finished_utc = new Date().toISOString();
fs.writeFileSync(destination, JSON.stringify(report, null, 2) + "\n");
console.log(`Completed ${report.steps.length} checks. Evidence: ${destination}`);
