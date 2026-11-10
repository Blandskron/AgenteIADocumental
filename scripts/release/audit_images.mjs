// Scan immutable final images; no app settings, DB, personal files or Docker socket in scanners.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";

const verificationEnvFile = process.env.VERIFICATION_ENV_FILE || ".env.example";
process.loadEnvFile(verificationEnvFile);

const root = fileURLToPath(new URL("../../", import.meta.url));
const args = process.argv.slice(2), project = args[args.indexOf("--project") + 1];
if (!args.includes("--project") || project !== "bd-final-check") throw Error("Use dedicated --project bd-final-check");
const destination = path.resolve(args.includes("--out") ? args[args.indexOf("--out") + 1] : "docs/release/IMAGE_AUDIT.json");
const scanner = "aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb";
const services = {
  "auth-service": ["AuthServices", 10001], "conversation-service": ["ConversationServices", 10002],
  "rag-document-chat-service": ["RagDocumentChatServices", 10003],
  "rag-document-embedding-service": ["RagDocumentEmbeddingServices", 10004],
  "document-search-service": ["DocumentSearchServices", 10005],
  "document-access-service": ["DocumentAccessServices", 10004],
  "document-library-service": ["DocumentLibraryServices", 10006],
  "document-transfer-service": ["DocumentTransferServices", 10007], "profile-service": ["ProfileServices", 10008],
  "document-export-service": ["DocumentExportServices", 10009],
  "google-drive-import-service": ["GoogleDriveImportServices", 10010], "blandskron-frontend": [null, 101],
};
function docker(argv, input) {
  const result = spawnSync("docker", argv, { input, encoding: "utf8", maxBuffer: 128 * 1024 * 1024, shell: false });
  if (result.status !== 0) throw Error(`Docker ${argv[0]} failed: ${(result.stderr || "").slice(-2000)}`);
  return result.stdout.trim();
}
const hash = (data) => createHash("sha256").update(data).digest("hex");
function inputs(folder) {
  const walk = (directory) => fs.readdirSync(path.join(root, directory), { withFileTypes: true }).flatMap((entry) => {
    if (["__pycache__", "node_modules", "dist", ".git"].includes(entry.name) || entry.name.endsWith(".pyc")) return [];
    const name = `${directory}/${entry.name}`;
    return entry.isDirectory() ? walk(name) : [name];
  });
  const appFiles = folder === "AuthServices" ? [...walk("backend/AuthServices/core"), ...walk("backend/AuthServices/users"),
    "backend/AuthServices/entrypoint.sh", "backend/AuthServices/manage.py"] : folder ? walk(`backend/${folder}/app`) : [];
  const files = folder ? [`backend/${folder}/Dockerfile`, `backend/${folder}/requirements.txt`, ...appFiles]
    : ["frontend/Dockerfile", "frontend/.dockerignore", "frontend/nginx.conf", "frontend/package.json", "frontend/package-lock.json",
      "frontend/tsconfig.json", "frontend/vite.config.ts", "frontend/public/runtime-config.js", "frontend/public/blandskron.svg",
      "frontend/index.html", ...walk("frontend/docker-entrypoint.d"), ...walk("frontend/src")];
  return files.sort().map((file) => ({ path: file, sha256: hash(fs.readFileSync(path.join(root, file), "utf8").replaceAll("\r\n", "\n")) }));
}
const work = args.includes("--work") ? fs.realpathSync(args[args.indexOf("--work") + 1]) : fs.mkdtempSync(path.join(os.tmpdir(), "bd-release-audit-"));
// Windows may spell TEMP with an 8.3 alias; compare directory identity, not spelling.
const tempIdentity = fs.statSync(os.tmpdir(), { bigint: true });
const parentIdentity = fs.statSync(path.dirname(work), { bigint: true });
if (!tempIdentity.ino || tempIdentity.dev !== parentIdentity.dev || tempIdentity.ino !== parentIdentity.ino
  || !path.basename(work).startsWith("bd-release-audit-")) throw Error("Owned temporary audit directory required");
const report = args.includes("--resume") ? JSON.parse(fs.readFileSync(destination, "utf8")) : { card: "PLAT-002", date_utc: new Date().toISOString(), scanner_image: scanner,
  severity_filter: ["HIGH", "CRITICAL"], source_normalization: "UTF-8 LF", images: [], requires_review: [] };
if (report.card !== "PLAT-002" || report.scanner_image !== scanner) throw Error("Incompatible audit evidence");
const inspector = fs.readFileSync(path.join(root, "scripts/release/inspect_runtime.py"));
for (const [service, [folder, uid]] of Object.entries(services)) {
  const tag = `${project}-${service}`;
  const id = docker(["image", "inspect", "--format", "{{.Id}}", tag]);
  if (!/^sha256:[a-f0-9]{64}$/.test(id)) throw Error("Immutable image ID required");
  const compose = ["compose", "--env-file", verificationEnvFile, "-p", project, "-f", "docker/docker-compose.yml", "-f", "docker/compose/verification.yml"];
  const container = docker([...compose, "ps", "-q", service]);
  if (!container || docker(["inspect", "--format", "{{.Image}}", container]) !== id) throw Error(`Running image mismatch: ${service}`);
  const effectiveUid = folder ? Number(docker([...compose, "exec", "-T", service, "python", "-c",
    "print(next(line.split()[1] for line in open('/proc/1/status') if line.startswith('Uid:')))"]))
    : Number(docker([...compose, "exec", "-T", service, "id", "-u"]));
  if (effectiveUid !== uid) report.requires_review.push(`${service}: unexpected effective PID1 user`);
  const previous = report.images.find((entry) => entry.service === service);
  const currentInputs = inputs(folder);
  if (previous?.image_id === id) {
    if (JSON.stringify(previous.build_inputs) !== JSON.stringify(currentInputs)) throw Error(`Sources changed without rebuilding ${service}`);
    console.log(JSON.stringify({ service, reused_verified_image: id }));
    continue;
  }
  const archive = path.join(work, "image.tar");
  docker(["save", "--output", archive, id]);
  const owner = fs.statSync(archive);
  const reader = `${project}-auth-service`;
  const savedConfig = docker(["run", "--rm", "--user", `${owner.uid}:${owner.gid}`, "--network", "none", "--read-only",
    "--cap-drop=ALL", "--security-opt=no-new-privileges:true", "--mount", `type=bind,source=${archive},target=/image.tar,readonly`,
    "--entrypoint", "python", reader, "-c",
    "import tarfile,json,hashlib; t=tarfile.open('/image.tar'); m=json.load(t.extractfile('manifest.json')); assert len(m)==1; print('sha256:'+hashlib.sha256(t.extractfile(m[0]['Config']).read()).hexdigest())"]);
  const digest = createHash("sha256");
  for await (const chunk of fs.createReadStream(archive)) digest.update(chunk);
  let inventory = null;
  if (folder) {
    inventory = JSON.parse(docker(["run", "--rm", "-i", "--user", String(uid), "--network", "none", "--read-only",
      "--cap-drop=ALL", "--security-opt=no-new-privileges:true", "--entrypoint", "python", id, "-"], inspector));
    if (Object.keys(inventory.packages).some((name) => ["pip", "pytest", "ruff", "pip-audit"].includes(name.toLowerCase()))) {
      report.requires_review.push(`${service}: unexpected installer/test/audit distribution`);
    }
  } else {
    const user = docker(["run", "--rm", "--network", "none", "--entrypoint", "id", id, "-u"]);
    if (Number(user) !== uid) report.requires_review.push(`${service}: unexpected runtime user`);
  }
  docker(["run", "--rm", "--mount", `type=bind,source=${work},target=/audit`, scanner, "image", "--scanners", "vuln",
    "--timeout", "15m", "--severity", "HIGH,CRITICAL", "--format", "json", "--output", "/audit/scan.json", "--cache-dir", "/audit/cache", "--input", "/audit/image.tar"]);
  const scan = JSON.parse(fs.readFileSync(path.join(work, "scan.json"), "utf8"));
  if (scan.Metadata?.ImageID !== savedConfig) throw Error(`Scanner image identity mismatch: ${service}`);
  const findings = (scan.Results || []).flatMap((result) => (result.Vulnerabilities || []).map((v) => ({
    id: v.VulnerabilityID, package: v.PkgName, installed: v.InstalledVersion, fixed: v.FixedVersion || null,
    severity: v.Severity, target: result.Target, class: result.Class,
    disposition: result.Class === "os-pkgs" && !v.FixedVersion && v.Severity === "HIGH"
      ? "Residual OS advisory without fix indicated; local loopback portfolio scope, rebuild/rescan before any deployment."
      : "REQUIRES_REVIEW",
  })));
  const entry = { service, image_id: id, effective_uid: effectiveUid, archive_sha256: digest.digest("hex"), saved_config_id: savedConfig, scanned_image_id: scan.Metadata.ImageID,
    collected_utc: new Date().toISOString(), os: scan.Metadata.OS, inventory, build_inputs: currentInputs, findings,
    counts: { high: findings.filter((v) => v.severity === "HIGH").length, critical: findings.filter((v) => v.severity === "CRITICAL").length,
      fixed_available: findings.filter((v) => v.fixed).length, unique_ids: new Set(findings.map((v) => v.id)).size } };
  report.images = report.images.filter((item) => item.service !== service);
  report.images.push(entry);
  report.requires_review = report.images.flatMap((item) => [
    ...item.findings.filter((v) => v.disposition === "REQUIRES_REVIEW").map((v) => `${item.service}: ${v.id} ${v.package}`),
    ...(item.effective_uid !== services[item.service][1] ? [`${item.service}: unexpected effective user`] : []),
    ...(Object.keys(item.inventory?.packages || {}).some((name) => ["pip", "pytest", "ruff", "pip-audit"].includes(name.toLowerCase())) ? [`${item.service}: unexpected installer/test tooling`] : []),
    ...(item.inventory?.ensurepip_present ? [`${item.service}: bootstrap installer remains`] : []),
  ]);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.writeFileSync(destination, JSON.stringify(report, null, 2) + "\n");
  fs.unlinkSync(archive);
  console.log(JSON.stringify({ service, image: id, counts: entry.counts }));
}
// Cache contains scanner databases only. Keep it private outside Git for a later rescan.
console.log(JSON.stringify({ completed: report.images.length, requires_review: report.requires_review }));
report.finished_utc = new Date().toISOString();
report.audit_tool_sha256 = hash(fs.readFileSync(fileURLToPath(import.meta.url)));
report.inventory_tool_sha256 = hash(inspector);
fs.writeFileSync(destination, JSON.stringify(report, null, 2) + "\n");
if (report.requires_review.length) process.exitCode = 1;
