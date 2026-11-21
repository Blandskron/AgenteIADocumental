#!/usr/bin/env node
/**
 * Automated real-application screenshot generator for Blandskron Documental.
 *
 * Usage (with Docker Compose stack running at http://localhost:3000):
 *   node scripts/screenshots/capture_screenshots.mjs --base-url http://localhost:3000
 *
 * Requires Playwright (installed in frontend/node_modules/@playwright/test)
 * and optionally `cwebp` for WebP compression (falls back to PNG if unavailable).
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");
const OUT_DIR = path.join(ROOT, "docs", "assets", "screenshots");
const REPORT_FILE = path.join(ROOT, ".release-reports", "SCREENSHOTS_REPORT.json");

function parseArgs(argv) {
  const args = {
    baseUrl: process.env.SCREENSHOTS_BASE_URL || "http://localhost:3000",
    authUrl: process.env.SCREENSHOTS_AUTH_URL || "http://localhost:8001",
    username: process.env.SCREENSHOTS_USERNAME || "demo_screenshots",
    email: process.env.SCREENSHOTS_EMAIL || "demo_screenshots@synthetic.local",
    password: process.env.SCREENSHOTS_PASSWORD || "SyntheticDemo!2026#",
  };
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === "--base-url" && argv[i + 1]) args.baseUrl = argv[++i];
    if (argv[i] === "--auth-url" && argv[i + 1]) args.authUrl = argv[++i];
  }
  return args;
}

function hasCwebp() {
  try {
    execFileSync("cwebp", ["-version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function saveOptimized(pngPath, baseName, useWebp) {
  if (!useWebp) return pngPath;
  const webpPath = path.join(OUT_DIR, `${baseName}.webp`);
  execFileSync("cwebp", ["-q", "84", "-quiet", pngPath, "-o", webpPath]);
  fs.unlinkSync(pngPath);
  return webpPath;
}

async function ensureSyntheticAccount(args) {
  const regResp = await fetch(`${args.authUrl}/api/users/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: args.email,
      username: args.username,
      password: args.password,
      workspace_name: "Espacio Sintético Demo",
    }),
  });
  if (regResp.ok) return await regResp.json();

  const loginResp = await fetch(`${args.authUrl}/api/users/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: args.username, password: args.password }),
  });
  if (!loginResp.ok) {
    throw new Error(`No se pudo autenticar cuenta sintética (HTTP ${loginResp.status}).`);
  }
  return await loginResp.json();
}

async function main() {
  const args = parseArgs(process.argv);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.mkdirSync(path.dirname(REPORT_FILE), { recursive: true });

  // Verify live stack availability before launching browser
  const health = await fetch(args.baseUrl).catch(() => null);
  if (!health || !health.ok) {
    throw new Error(
      `La aplicación no responde en ${args.baseUrl}. Levanta el stack con: docker compose up -d --build`,
    );
  }

  const { chromium } = await import(
    path.join(ROOT, "frontend", "node_modules", "@playwright", "test", "index.mjs")
  );
  const useWebp = hasCwebp();
  const report = {
    generated_at: new Date().toISOString(),
    base_url: args.baseUrl,
    format: useWebp ? "webp" : "png",
    captured: [],
    omitted: [],
  };

  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    async function snap(name, route, waitMs = 900) {
      try {
        await page.goto(`${args.baseUrl}${route}`, { waitUntil: "networkidle", timeout: 15000 });
        await page.waitForTimeout(waitMs);
        const pngPath = path.join(OUT_DIR, `${name}.png`);
        await page.screenshot({ path: pngPath, fullPage: false });
        const finalPath = saveOptimized(pngPath, name, useWebp);
        report.captured.push({ name, route, file: path.relative(ROOT, finalPath) });
      } catch (err) {
        report.omitted.push({ name, route, reason: String(err.message || err) });
      }
    }

    // 1. Public screens
    await snap("login", "/login");

    // 2. Authenticate with synthetic account
    const authPayload = await ensureSyntheticAccount(args);
    await page.addInitScript((session) => {
      localStorage.setItem("blandskron.auth", JSON.stringify(session));
    }, {
      access: authPayload.access,
      refresh: authPayload.refresh,
      user: authPayload.user,
      username: args.username,
      sessionId: crypto.randomUUID(),
    });

    // 3. Authenticated desktop screens
    await snap("document-chat", "/");
    await snap("documents", "/documents");
    await snap("document-assignments", "/documents/assignments");
    await snap("notifications", "/documents/notifications");
    await snap("ai-settings", "/settings/ai");
    await snap("knowledge-studio", "/studio");
    await snap("admin-users", "/admin");
    await snap("audit-logs", "/admin/audit");
  } finally {
    await browser.close();
  }

  fs.writeFileSync(REPORT_FILE, `${JSON.stringify(report, null, 2)}\n`, "utf-8");
  console.log(`Captured ${report.captured.length} screenshots -> ${REPORT_FILE}`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
