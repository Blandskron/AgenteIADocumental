// Validate captured runtime metadata with test tooling, never install an inspector in runtime.
import fs from "node:fs";
import { spawnSync } from "node:child_process";

const filename = "docs/release/IMAGE_AUDIT.json";
const report = JSON.parse(fs.readFileSync(filename, "utf8"));
const images = report.images.filter((image) => image.inventory);
if (!report.finished_utc || images.length !== 11 || report.requires_review.length) throw Error("Complete the image audit first.");
const program = [
  "import io,json,runpy,sys",
  "data=json.load(sys.stdin)",
  "verify=runpy.run_path('/export-checks/verify_runtime_dependencies.py')['main']",
  "for image in data:",
  "    sys.stdin=io.StringIO(json.dumps(image['inventory']))",
  "    verify()",
].join("\n");
const result = spawnSync("docker", ["compose", "--env-file", ".env.example", "-p", "bd-final-check",
  "-f", "docker/docker-compose.yml", "-f", "docker/compose/verification.yml", "run", "--rm", "--no-deps", "-T",
  "export-tests", "python", "-c", program], { input: JSON.stringify(images), encoding: "utf8", maxBuffer: 4 * 1024 * 1024, shell: false });
if (result.status !== 0) throw Error(`Runtime graph check failed: ${(result.stderr || "").slice(-2000)}`);
report.runtime_graph_verification = { checked_utc: new Date().toISOString(), python_images: images.length,
  extras: { uvicorn: ["standard"], psycopg: ["binary"] }, exit_code: result.status };
fs.writeFileSync(filename, JSON.stringify(report, null, 2) + "\n");
console.log(result.stdout.trim());
