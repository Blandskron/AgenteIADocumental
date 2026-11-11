// Cross-platform synthetic PostgreSQL/service checks. Never use with a personal project.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";

const verificationEnvFile = process.env.VERIFICATION_ENV_FILE || ".env.example";
process.loadEnvFile(verificationEnvFile);

const prefix = ["compose", "--env-file", verificationEnvFile, "-p", "bd-final-check", "-f", "docker/docker-compose.yml", "-f", "docker/compose/verification.yml"];
const folder = fs.mkdtempSync(path.join(os.tmpdir(), "bd-verification-"));
const destination = ".release-reports/VERIFICATION.json";
const demoOnly = process.argv.includes("--demo-only");
const relationsOnly = process.argv.includes("--relations-only");
const report = demoOnly || relationsOnly ? JSON.parse(fs.readFileSync(destination, "utf8")) : { cards: ["PLAT-001", "DEMO-001"], started_utc: new Date().toISOString(),
  source_commit: spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).stdout.trim(), steps: [] };
if (demoOnly) {
  const start = report.steps.findIndex(step => step.label === "end-to-end synthetic demo");
  const baseline = start < 0 ? report.steps : report.steps.slice(0, start);
  if (baseline.some(step => step.exit_code !== 0)) throw Error("Resolve earlier checks first");
  report.previous_demo_attempts = [...(report.previous_demo_attempts || []), ...(start < 0 ? [] : report.steps.slice(start))];
  report.steps = baseline;
}
async function check(label, args, compose = true) {
  const start = Date.now(), log = path.join(folder, `${report.steps.length}.log`);
  const output = fs.openSync(log, "w");
  console.log(`Checking ${label}`);
  const child = spawn("docker", [...(compose ? prefix : []), ...args], { stdio: ["ignore", output, output], shell: false });
  const code = await new Promise((resolve, reject) => { child.once("error", reject); child.once("exit", resolve); });
  fs.closeSync(output);
  report.steps.push({ label, exit_code: code, seconds: Math.round((Date.now()-start)/1000) });
  if (label === "end-to-end synthetic demo" && code === 0) {
    for (const line of fs.readFileSync(log, "utf8").split(/\r?\n/)) {
      if (!line.startsWith("{")) continue;
      try { const data = JSON.parse(line); if (data.card === "DEMO-001") report.steps.at(-1).details = data; } catch { /* progress only */ }
    }
  }
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.writeFileSync(destination, JSON.stringify(report, null, 2) + "\n");
  if (code !== 0) throw Error(`${label} failed; private log ${log}\n${fs.readFileSync(log, "utf8").slice(-6000)}`);
  console.log(`Passed ${label} (${report.steps.at(-1).seconds}s)`);
}
const sql = (db, script) => ["run", "--rm", "--no-deps", "database-schema", "psql", "-h", "postgres", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-q", "-f", `/schema/${script}`];
if (!demoOnly && !relationsOnly) {
await check("Compose", ["config", "--quiet"]);
await check("storage initializes empty directory and preserves inaccessible existing files", ["run", "--rm", "--network", "none",
  "--label", "blandskron.synthetic=bd-final-check", "--entrypoint", "sh", "-e", "DOCUMENT_UID=10004", "-e", "DOCUMENT_GID=10004",
  "--volume", `${path.resolve("docker/scripts/prepare_documents.sh")}:/prepare_documents.sh:ro`, "pgvector/pgvector:pg16", "-c",
  'mkdir /documents && if DOCUMENT_UID=00 sh /prepare_documents.sh; then exit 1; fi && sh /prepare_documents.sh && test "$(stat -c %u /documents)" = 10004 && chown 0:0 /documents && chmod 700 /documents && printf synthetic >/documents/sentinel && if sh /prepare_documents.sh; then exit 1; fi && test "$(stat -c %u /documents)" = 0 && test "$(cat /documents/sentinel)" = synthetic'], false);
await check("tenant preflight with active constraints", sql("documents_db", "tests/tenant_preflight.sql"));
for (const script of ["auth/verify_roles.sql", "conversation/verify_role.sql", "rag-chat/verify_role.sql", "embedding/verify_role.sql",
  "search/verify_role.sql", "access/verify_role.sql", "library/verify_role.sql", "transfer/verify_role.sql", "profile/verify_role.sql", "export/verify_role.sql", "drive/verify_role.sql"]) {
  await check(script, sql("documents_db", script));
}
await check("Auth regression", ["exec", "-T", "-e", "POSTGRES_USER=postgres", "-e", `POSTGRES_PASSWORD=${process.env.POSTGRES_PASSWORD}`, "auth-service", "python", "manage.py", "test", "users", "core", "--noinput"]);
for (const service of ["conversation-tests", "rag-chat-tests", "embedding-tests", "search-tests", "access-tests", "library-tests", "transfer-tests", "profile-tests", "export-tests", "drive-tests"]) {
  await check(service, ["run", "--build", "--rm", "--no-deps", service]);
  await check(`${service} Ruff`, ["run", "--rm", "--no-deps", service, "ruff", "check", "--no-cache", "app", "tests"]);
}
}
if (!demoOnly) {
for (const [kind, script] of [["assignments", "test_tenant_assignments.py"], ["relations", "test_tenant_area_relations.py"], ["hierarchy", "test_tenant_hierarchy.py"], ["identity", "test_tenant_user_links.py"]]) {
  const db = `plat_${kind}_release`;
  const admin = (query) => ["exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "documents_db", "-v", "ON_ERROR_STOP=1", "-c", query];
  await check(`create ${db}`, admin(`CREATE DATABASE ${db}`));
  try {
    await check(`${db} bootstrap`, sql(db, "run_all.sql"));
    if (kind === "identity") {
      await check(`${db} Auth roles`, ["run", "--rm", "--no-deps", "auth-db-roles", "psql", "-h", "postgres", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-f", "/auth-db/provision_roles.sql"]);
      await check(`${db} Django`, ["run", "--rm", "--no-deps", "-e", `POSTGRES_DB=${db}`, "auth-migrate"]);
      await check(`${db} activate`, sql(db, "migrations/006_tenant_user_links.sql"));
    }
    for (const [source, target] of [["002_tenant_assignments.sql", "tenant-assignments.sql"], ["003_tenant_area_relations.sql", "tenant-areas.sql"], ["004_tenant_hierarchy.sql", "tenant-hierarchy.sql"], ["005_tenant_user_links.sql", "tenant-user-links.sql"]]) {
      await check(`${db} stage ${source}`, ["cp", `scripts/database/constraints/${source}`, `auth-service:/tmp/${target}`]);
    }
    await check(`${db} stage tests`, ["cp", `scripts/database/tests/${script}`, `auth-service:/tmp/${script}`]);
    await check(`${db} regressions`, ["exec", "-T", "-e", `POSTGRES_DB=${db}`, "-e", `PLAT_TEST_DATABASE=${db}`, "-e", `PLAT_TEST_ADMIN_PASSWORD=${process.env.POSTGRES_PASSWORD}`, "auth-service", "python", `/tmp/${script}`]);
    if (kind === "relations") {
      await check(`${db} embedding role`, ["run", "--rm", "--no-deps", "-e", "EMBEDDING_DB_PASSWORD=blandskron-local-embedding", "database-schema", "psql", "-h", "postgres", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-f", "/schema/embedding/provision_role.sql"]);
      await check(`${db} embedding races`, ["run", "--rm", "--no-deps", "--volume", `${process.cwd()}/scripts/database/tests:/relation-checks:ro`, "-e", "PYTHONPATH=/app", "-e", `PLAT_TEST_DATABASE=${db}`, "-e", `PLAT_TEST_ADMIN_PASSWORD=${process.env.POSTGRES_PASSWORD}`, "-e", "PLAT_TEST_AUTH_PASSWORD=blandskron-local-runtime", "embedding-tests", "python", "/relation-checks/test_embedding_area_relations.py"]);
    }
  } finally { await check(`drop ${db}`, admin(`DROP DATABASE ${db} WITH (FORCE)`)); }
}
}
if (!relationsOnly) {
  await check("end-to-end synthetic demo", ["run", "--rm", "--no-deps", "export-tests", "python", "/verification/demo_flow.py"]);
  await check("lost upload response cleanup", ["run", "--rm", "--no-deps", "-e", "DEMO_LOST_UPLOAD_RESPONSE=1", "export-tests", "python", "/verification/demo_flow.py"]);
  const probe = `bd-final-check-persistence-${Date.now()}`;
  await check("start private persistence probe", ["run", "-d", "--no-deps", "--name", probe,
    "-e", `INITIAL_ADMIN_USERNAME=${process.env.INITIAL_ADMIN_USERNAME}`,
    "-e", `INITIAL_ADMIN_PASSWORD=${process.env.INITIAL_ADMIN_PASSWORD}`, "export-tests", "sleep", "1800"]);
  try {
    await check("bootstrap login, upload and password change", ["exec", probe, "python", "/verification/persistence_probe.py", "prepare"], false);
    await check("stop dedicated stack preserving volumes", ["stop"]);
    await check("restart with bootstrap and existing volumes", ["up", "-d", "--wait", "blandskron-frontend"]);
    await check("password and document preserved after restart", ["exec", probe, "python", "/verification/persistence_probe.py", "verify"], false);
    await check("second idempotent startup", ["up", "-d", "--wait", "blandskron-frontend"]);
    await check("no duplicated users or documents", ["exec", probe, "python", "/verification/persistence_probe.py", "verify"], false);
  } finally {
    // Recover only fixtures in this probe, even if a restart/check failed.
    try { await check("remove persistence fixtures", ["exec", probe, "python", "/verification/persistence_probe.py", "cleanup"], false); }
    finally { await check("remove private probe container", ["rm", "-f", probe], false); }
  }
  await check("synthetic postflight: zero fixtures", sql("documents_db", "tests/release_cleanup.sql"));
}
report.finished_utc = new Date().toISOString();
fs.writeFileSync(destination, JSON.stringify(report, null, 2) + "\n");
console.log(`Completed ${report.steps.length} checks. Evidence: ${destination}`);
