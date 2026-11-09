// Host orchestration only; scanners receive an immutable archive, never the repository or .env.
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const imageArg = args[args.indexOf("--image") + 1], outArg = args[args.indexOf("--out") + 1];
if (!args.includes("--image") || !args.includes("--out") || !imageArg || !outArg) throw new Error("--image and --out required");
const out = path.resolve(outArg), root = fileURLToPath(new URL("../../", import.meta.url));
const scanner = "aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb";
const base = "backend/GoogleDriveImportServices";
function docker(argv, input) {
  const result = spawnSync("docker", argv, { input, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, shell: false });
  if (result.status !== 0 || result.error) throw new Error(`Docker audit step failed: ${argv[0]} (${result.status}): ${(result.stderr || result.error?.message || "").slice(-4000)}`);
  return result.stdout.trim();
}
function hash(data) { return createHash("sha256").update(data).digest("hex"); }
fs.mkdirSync(out, { mode: 0o700 }); // Refuse to overwrite evidence; keep artifacts private.
const image = docker(["image", "inspect", "--format", "{{.Id}}", imageArg]);
if (!/^sha256:[a-f0-9]{64}$/.test(image)) throw new Error("Expected immutable image ID");
const archive = path.join(out, "runtime-image.tar");
docker(["save", "--output", archive, image]);
// docker save may create a 0600 archive on Linux. Only this offline, read-only
// artifact reader uses the archive owner; runtime inventory still checks UID 10010.
const archiveOwner = fs.statSync(archive);
const savedConfig = docker(["run", "--rm", "--user", `${archiveOwner.uid}:${archiveOwner.gid}`, "--cap-drop=ALL", "--security-opt=no-new-privileges:true", "--network", "none", "--read-only", "--mount", `type=bind,source=${archive},target=/runtime-image.tar,readonly`,
  "--entrypoint", "python", image, "-c", "import tarfile,json,hashlib; t=tarfile.open('/runtime-image.tar'); m=json.load(t.extractfile('manifest.json')); assert len(m)==1; print('sha256:'+hashlib.sha256(t.extractfile(m[0]['Config']).read()).hexdigest())"]);
const digest = createHash("sha256");
for await (const chunk of fs.createReadStream(archive)) digest.update(chunk);
const runtime = JSON.parse(docker(["run", "--rm", "-i", "--network", "none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
  "--entrypoint", "python", image, "-"], fs.readFileSync(path.join(root, "scripts/drive/inspect_runtime.py"))));
fs.writeFileSync(path.join(out, "runtime.json"), JSON.stringify(runtime, null, 2) + "\n");
docker(["run", "--rm", "--mount", `type=bind,source=${out},target=/audit`, scanner, "image", "--scanners", "vuln", "--severity", "HIGH,CRITICAL",
  "--format", "json", "--output", "/audit/trivy.json", "--cache-dir", "/tmp/trivy-cache", "--input", "/audit/runtime-image.tar"]);
const scan = JSON.parse(fs.readFileSync(path.join(out, "trivy.json"), "utf8"));
const findings = (scan.Results || []).flatMap((result) => (result.Vulnerabilities || []).map((v) => ({
  id: v.VulnerabilityID, package: v.PkgName, installed: v.InstalledVersion, fixed: v.FixedVersion || null,
  severity: v.Severity, target: result.Target,
  disposition: result.Class === "os-pkgs" && !v.FixedVersion && v.Severity === "HIGH" ? "DRIVE-F01: OS without fix indicated; rebuild/rescan before public deployment (PLAT-002)." : "REQUIRES_REVIEW",
})));
function walk(dir) { return fs.readdirSync(path.join(root, dir), { withFileTypes: true }).flatMap((entry) => {
  const name = `${dir}/${entry.name}`;
  if (entry.name === "__pycache__" || entry.name.endsWith(".pyc")) return [];
  return entry.isDirectory() ? walk(name) : [name];
}); }
const inputs = [`${base}/Dockerfile`, `${base}/requirements.txt`, ...walk(`${base}/app`)].sort().map((name) => ({
  path: name, sha256: hash(fs.readFileSync(path.join(root, name), "utf8").replaceAll("\r\n", "\n")),
}));
const report = { card: "DRIVE-007/008", date_utc: new Date().toISOString(), scanner: "Trivy 0.76.2", scanner_image: scanner,
  severity_filter: ["HIGH", "CRITICAL"], runtime_image_id: image, archive_sha256: digest.digest("hex"), saved_config_id: savedConfig, scanned_config_id: scan.Metadata?.ImageID,
  base: fs.readFileSync(path.join(root, base, "Dockerfile"), "utf8").split(/\r?\n/)[0], os: scan.Metadata?.OS, runtime,
  source_hash_normalization: "UTF-8 LF for runtime source text", build_inputs: inputs, build_inputs_sha256: hash(JSON.stringify(inputs)),
  findings, counts: { matches: findings.length, unique_ids: new Set(findings.map((v) => v.id)).size, critical: findings.filter((v) => v.severity === "CRITICAL").length } };
fs.writeFileSync(path.join(out, "IMAGE_AUDIT.json"), JSON.stringify(report, null, 2) + "\n");
fs.unlinkSync(archive);
console.log(JSON.stringify({ image, counts: report.counts }));
if (scan.Metadata?.ImageID !== savedConfig || runtime.uid !== 10010 || ["pip", "pytest", "ruff", "pip-audit"].some((name) => Object.keys(runtime.packages).map((v) => v.toLowerCase()).includes(name)) || findings.some((v) => v.disposition === "REQUIRES_REVIEW")) {
  throw new Error("Runtime audit requires explicit review; full evidence retained");
}
