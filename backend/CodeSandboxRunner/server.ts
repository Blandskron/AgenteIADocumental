/**
 * Hardened Code Mode Sandbox Runner (AG-010).
 *
 * Security invariants (ADR-007):
 * - Exposed ONLY on internal Docker network (`internal: true`), never published to 127.0.0.1 or internet.
 * - Executes untrusted agent code in an isolated child Deno V8 isolate with `--deny-all --no-remote --no-npm`.
 * - Clears all environment variables (`clearEnv: true`) before spawning the child process.
 * - Enforces strict wall-clock timeout (`CODE_SANDBOX_TIMEOUT_MS`, default 5000ms) and output cap.
 * - Never uses `eval()`, `Function()`, `exec()` or `node:vm` in the host process.
 */

const PORT = Number(Deno.env.get("PORT") ?? "8090");
const DEFAULT_TIMEOUT_MS = Math.min(
  10000,
  Math.max(500, Number(Deno.env.get("CODE_SANDBOX_TIMEOUT_MS") ?? "5000")),
);
const MAX_CODE_BYTES = 8192;
const MAX_OUTPUT_BYTES = 65536;

const FORBIDDEN_PATTERNS: RegExp[] = [
  /\bDeno\.(env|readFile|writeFile|run|Command|open|listen|connect)\b/,
  /\b(fetch|WebSocket|XMLHttpRequest)\s*\(/,
  /\bimport\s+.*from\s+['"]https?:\/\//,
  /\bprocess\.env\b/,
];

interface ExecutePayload {
  code?: unknown;
  data?: unknown;
  timeout_ms?: unknown;
}

function jsonResponse(body: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function runIsolatedScript(
  code: string,
  data: unknown,
  timeoutMs: number,
): Promise<Record<string, unknown>> {
  const started = performance.now();
  const tempFile = await Deno.makeTempFile({ dir: "/tmp", prefix: "cm_", suffix: ".ts" });

  // Wrap user module cleanly in a temporary file executed by a separate `--deny-all` Deno process.
  const harness = `
const __INPUT_DATA__ = ${JSON.stringify(data ?? {})};
${code}
if (typeof transform === "function") {
  const __result__ = await transform(__INPUT_DATA__);
  console.log("__CM_RESULT__" + JSON.stringify(__result__));
}
`;

  try {
    await Deno.writeTextFile(tempFile, harness);

    const command = new Deno.Command("deno", {
      args: [
        "run",
        "--deny-all",
        "--no-remote",
        "--no-npm",
        "--no-prompt",
        "--v8-flags=--max-old-space-size=128",
        tempFile,
      ],
      clearEnv: true,
      stdin: "null",
      stdout: "piped",
      stderr: "piped",
    });

    const child = command.spawn();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      try {
        child.kill("SIGKILL");
      } catch {
        // Process already exited.
      }
    }, timeoutMs);

    const { code: exitCode, stdout, stderr } = await child.output();
    clearTimeout(timer);
    const durationMs = Math.round(performance.now() - started);

    if (timedOut) {
      return { ok: false, error: `Timeout excedido (${timeoutMs}ms).`, duration_ms: durationMs };
    }

    const stdoutText = new TextDecoder().decode(stdout).slice(0, MAX_OUTPUT_BYTES);
    const stderrText = new TextDecoder().decode(stderr).slice(0, 4096);

    if (exitCode !== 0) {
      return {
        ok: false,
        error: stderrText || `Sandbox exited with code ${exitCode}`,
        duration_ms: durationMs,
      };
    }

    let parsedOutput: unknown = null;
    for (const line of stdoutText.split("\n")) {
      if (line.startsWith("__CM_RESULT__")) {
        try {
          parsedOutput = JSON.parse(line.slice("__CM_RESULT__".length));
        } catch {
          parsedOutput = line.slice("__CM_RESULT__".length);
        }
      }
    }

    return {
      ok: true,
      output: parsedOutput,
      stdout: stdoutText.replace(/^__CM_RESULT__.*$/gm, "").trim(),
      duration_ms: durationMs,
    };
  } finally {
    try {
      await Deno.remove(tempFile);
    } catch {
      // Ignore cleanup errors.
    }
  }
}

Deno.serve({ hostname: "0.0.0.0", port: PORT }, async (req: Request): Promise<Response> => {
  const url = new URL(req.url);
  if (req.method === "GET" && url.pathname === "/health") {
    return jsonResponse({ status: "ok", runtime: "deno-deny-all" });
  }
  if (req.method !== "POST" || url.pathname !== "/execute") {
    return jsonResponse({ ok: false, error: "Not found" }, 404);
  }

  let payload: ExecutePayload;
  try {
    payload = (await req.json()) as ExecutePayload;
  } catch {
    return jsonResponse({ ok: false, error: "Invalid JSON payload" }, 400);
  }

  const code = typeof payload.code === "string" ? payload.code.trim() : "";
  if (!code || new TextEncoder().encode(code).length > MAX_CODE_BYTES) {
    return jsonResponse({ ok: false, error: "Script vacío o excede 8192 bytes." }, 400);
  }
  for (const pattern of FORBIDDEN_PATTERNS) {
    if (pattern.test(code)) {
      return jsonResponse({ ok: false, error: "API bloqueada por política del sandbox." }, 403);
    }
  }

  const requestedTimeout = Number(payload.timeout_ms ?? DEFAULT_TIMEOUT_MS);
  const timeoutMs = Number.isFinite(requestedTimeout)
    ? Math.min(10000, Math.max(500, requestedTimeout))
    : DEFAULT_TIMEOUT_MS;

  const result = await runIsolatedScript(code, payload.data, timeoutMs);
  return jsonResponse(result, result.ok ? 200 : 422);
});
