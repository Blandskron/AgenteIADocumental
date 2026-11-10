// Real built frontend + real Auth, reached through docker exec without publishing
// synthetic services on the host. This bridge forwards bytes; it does not mock APIs.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";

if (!process.env.VERIFICATION_ENV_FILE) throw Error("Use a private synthetic verification environment");
process.loadEnvFile(process.env.VERIFICATION_ENV_FILE);
if (process.env.INITIAL_ADMIN_USERNAME !== "synthetic-release-admin") throw Error("Synthetic administrator required");
const require = createRequire(new URL("../../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const services = { 3000: "blandskron-frontend:8080", 8001: "auth-service:8001", 8002: "rag-document-chat-service:8000",
  8003: "rag-document-embedding-service:8000", 8004: "document-search-service:8000", 8005: "document-access-service:8000",
  8006: "document-library-service:8000", 8007: "document-transfer-service:8000", 8008: "conversation-service:8000",
  8015: "profile-service:8000", 8016: "document-export-service:8000", 8017: "google-drive-import-service:8000" };
const bridge = `import base64,json,sys,urllib.request,urllib.error
x=json.load(sys.stdin)
r=urllib.request.Request(x['url'], data=base64.b64decode(x['body']) if x['body'] else None, headers=x['headers'],method=x['method'])
try:
    response=urllib.request.build_opener(urllib.request.ProxyHandler({})).open(r,timeout=30)
except urllib.error.HTTPError as error:
    response=error
with response:
    print(json.dumps({'status':response.status,'headers':dict(response.headers),'body':base64.b64encode(response.read()).decode()}))`;
function forward(input) {
  return new Promise((resolve, reject) => {
    const child = spawn("docker", ["compose", "--env-file", process.env.VERIFICATION_ENV_FILE, "-p", "bd-final-check",
      "-f", "docker/docker-compose.yml", "-f", "docker/compose/verification.yml", "exec", "-T", "auth-service", "python", "-c", bridge],
    { stdio: ["pipe", "pipe", "pipe"], shell: false });
    let data = "";
    child.stdout.on("data", chunk => { data += chunk; });
    child.stderr.resume();
    child.on("error", reject);
    child.on("exit", code => {
      if (code !== 0) reject(Error("Synthetic browser bridge failed"));
      else { try { resolve(JSON.parse(data)); } catch { reject(Error("Invalid bridge response")); } }
    });
    child.stdin.end(JSON.stringify(input));
  });
}
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ serviceWorkers: "block" });
  let authenticated = false;
  await page.route("**/*", async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.hostname !== "localhost" || !services[url.port]) return route.abort();
    const headers = { ...request.headers() };
    for (const name of ["host", "content-length", "accept-encoding", "connection"]) delete headers[name];
    const result = await forward({ url: `http://${services[url.port]}${url.pathname}${url.search}`, method: request.method(),
      headers, body: request.postDataBuffer()?.toString("base64") || "" });
    if (url.port === "8001" && url.pathname === "/api/users/me/" && result.status === 200) authenticated = true;
    const returned = Object.fromEntries(Object.entries(result.headers).filter(([name]) => !["content-length", "transfer-encoding", "connection"].includes(name.toLowerCase())));
    await route.fulfill({ status: result.status, headers: returned, body: Buffer.from(result.body, "base64") });
  });
  await page.goto("http://localhost:3000", { timeout: 60000 });
  await page.getByLabel("Usuario").fill(process.env.INITIAL_ADMIN_USERNAME);
  await page.getByLabel(/^(Contraseña|Password)$/).fill(process.env.INITIAL_ADMIN_PASSWORD);
  const identityResponse = page.waitForResponse(response => response.url() === "http://localhost:8001/api/users/me/" && response.status() === 200);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await page.getByRole("button", { name: "synthetic-release-admin" }).waitFor({ timeout: 60000 });
  await identityResponse;
  if (!authenticated) throw Error("The browser did not authenticate against real Auth");
  console.log("Passed: built frontend login with bootstrapped administrator and real Auth/PostgreSQL (Docker byte bridge, no API mocks).");
} finally {
  await browser.close();
}
