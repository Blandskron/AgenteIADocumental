// Exercise the supported logical restore with disposable, network-isolated containers.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const legacy = "pgvector/pgvector@sha256:484e838076e04939d27d3e176e91c86eea96236126023be8d3059761122e579f";
const current = "bd-final-check-postgres";
const id = randomUUID();
const source = `bd-postgres-source-${id}`;
const target = `bd-postgres-target-${id}`;
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "bd-postgres-restore-"));
const files = ["roles.sql", "documents.dump"];
const containers = [];
const flags = ["--rm", "--network", "none", "--label", "blandskron.synthetic=bd-final-check"];

function docker(args, options = {}) {
  const result = spawnSync("docker", args, { encoding: "utf8", shell: false });
  if (result.error) throw result.error;
  if (!options.allowFailure && result.status !== 0) throw Error(`${args[0]} failed: ${result.stderr.trim()}`);
  return result;
}

async function start(name, image, initdbArgs) {
  docker(["run", "-d", ...flags, "--name", name, "-e", "POSTGRES_DB=documents_db",
    "-e", `POSTGRES_PASSWORD=${randomUUID()}`, "-e", `POSTGRES_INITDB_ARGS=${initdbArgs}`, image]);
  containers.push(name);
  for (let attempt = 0; attempt < 90; attempt++) {
    const ready = docker(["exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "documents_db"], { allowFailure: true });
    if (ready.status === 0) return;
    await delay(1000);
  }
  throw Error(`PostgreSQL did not become healthy in ${name}`);
}

function query(name, sql, role = "postgres") {
  return docker(["exec", name, "psql", "-X", "-At", "-U", role, "-d", "documents_db", "-v", "ON_ERROR_STOP=1", "-c", sql]).stdout.trim();
}

try {
  const currentImage = docker(["image", "inspect", "--format", "{{.Id}}", current]).stdout.trim();
  await start(source, legacy, "");
  docker(["cp", "scripts/database", `${source}:/tmp/schema`]);
  docker(["exec", source, "psql", "-X", "-q", "-U", "postgres", "-d", "documents_db", "-v", "ON_ERROR_STOP=1", "-f", "/tmp/schema/run_all.sql"]);
  query(source, "CREATE ROLE restore_reader LOGIN; CREATE TABLE retained (id int PRIMARY KEY, title text UNIQUE, embedding vector(3)); INSERT INTO retained VALUES (1, 'original', '[1,0,0]'); CREATE INDEX ON retained USING hnsw (embedding vector_cosine_ops); GRANT SELECT ON retained TO restore_reader;");
  const mounts = JSON.parse(docker(["inspect", "--format", "{{json .Mounts}}", source]).stdout);
  const volume = mounts.find((mount) => mount.Destination === "/var/lib/postgresql/data")?.Name;
  if (!volume) throw Error("Legacy PostgreSQL test volume not found");
  const guard = docker(["run", ...flags, "--mount", `type=volume,source=${volume},target=/var/lib/postgresql/data,readonly`, current], { allowFailure: true });
  if (guard.status === 0 || !guard.stderr.includes("Legacy PostgreSQL volume detected")) throw Error("Legacy data guard did not reject the volume");

  docker(["exec", source, "pg_dumpall", "-U", "postgres", "--roles-only", "-f", "/tmp/roles.sql"]);
  docker(["exec", source, "pg_dump", "-U", "postgres", "-Fc", "-f", "/tmp/documents.dump", "documents_db"]);
  await start(target, current, "--locale=C.UTF-8 --locale-provider=icu --icu-locale=en-US");
  docker(["exec", target, "mkdir", "-m", "700", "/tmp/restore"]);
  for (const file of files) {
    const local = path.join(directory, file);
    docker(["cp", `${source}:/tmp/${file}`, local]);
    docker(["cp", local, `${target}:/tmp/restore/${file}`]);
  }
  docker(["cp", "scripts/database/tools/restore_postgres16.sh", `${target}:/tmp/restore_postgres16.sh`]);
  docker(["exec", target, "sh", "/tmp/restore_postgres16.sh", "/tmp/restore"]);
  const migrated = query(target, "SELECT title FROM retained ORDER BY embedding <=> '[1,0,0]' LIMIT 1;", "restore_reader");
  const index = query(target, "SELECT count(*) FROM pg_indexes WHERE tablename = 'retained' AND indexdef LIKE '%USING hnsw%';");
  if (migrated !== "original" || index !== "1") throw Error("Logical restore failed to preserve data, grants or vector index");
  const duplicate = docker(["exec", target, "sh", "/tmp/restore_postgres16.sh", "/tmp/restore"], { allowFailure: true });
  if (duplicate.status === 0 || !duplicate.stderr.includes("Restore requires an empty documents_db.")) {
    throw Error("Restore did not reject a populated destination");
  }
  docker(["cp", "scripts/database", `${target}:/tmp/schema`]);
  docker(["exec", target, "psql", "-X", "-q", "-U", "postgres", "-d", "documents_db", "-v", "ON_ERROR_STOP=1", "-f", "/tmp/schema/run_all.sql"]);
  if (query(source, "SELECT title FROM retained") !== migrated) throw Error("Legacy data changed during the restore");
  const commit = spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf8", shell: false });
  if (commit.status !== 0) throw Error("Could not identify the source revision");
  fs.mkdirSync(".release-reports", { recursive: true });
  fs.writeFileSync(".release-reports/POSTGRES_UPGRADE.json", JSON.stringify({
    source_commit: commit.stdout.trim(), finished_utc: new Date().toISOString(),
    legacy_image: legacy, target_image: currentImage, result: "passed",
    checks: ["guard rejected legacy volume", "logical restore", "preserved row and access grant",
      "restored pgvector HNSW index", "guard rejected second restore", "schema bootstrap after restore", "legacy source unchanged"],
  }, null, 2) + "\n");
  console.log("Legacy data guard and logical PostgreSQL 16 restore passed with preserved role, data and pgvector index.");
} finally {
  for (const name of containers.reverse()) docker(["stop", name], { allowFailure: true });
  for (const file of files) fs.rmSync(path.join(directory, file), { force: true });
  fs.rmdirSync(directory);
}
