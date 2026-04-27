/**
 * Entrada de producción (p. ej. Render): Express sirve el SPA desde web/dist
 * y proxifica la API real (FastAPI / uvicorn) en un puerto loopback interno.
 */
import http from "node:http";
import crypto from "node:crypto";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import { createProxyMiddleware } from "http-proxy-middleware";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const webDist = path.join(repoRoot, "web", "dist");
const internalPort = String(process.env.HERMES_INTERNAL_PORT || "19119").replace(/[^0-9]/g, "") || "19119";
const internalTarget = `http://127.0.0.1:${internalPort}`;
const listenPort = Number(process.env.PORT || process.env.HERMES_EXPRESS_PORT || 3000);

const sessionToken =
  (process.env.HERMES_DASHBOARD_SESSION_TOKEN || "").trim() ||
  crypto.randomBytes(32).toString("base64url");
process.env.HERMES_DASHBOARD_SESSION_TOKEN = sessionToken;

function pythonExecutable() {
  const explicit = process.env.HERMES_PYTHON;
  if (explicit && fs.existsSync(explicit)) return explicit;
  const venvPy = path.join(repoRoot, ".venv", "bin", "python3");
  if (fs.existsSync(venvPy)) return venvPy;
  const venvPyWin = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(venvPyWin)) return venvPyWin;
  return process.platform === "win32" ? "python" : "python3";
}

function waitForBackend(url, maxMs = 120000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = async () => {
      if (Date.now() - start > maxMs) {
        reject(new Error(`Timeout esperando API en ${url}`));
        return;
      }
      try {
        const r = await fetch(`${url}/api/status`);
        if (r.ok) {
          resolve();
          return;
        }
      } catch {
        /* retry */
      }
      setTimeout(tick, 250);
    };
    tick();
  });
}

let cachedIndexHtml = null;
function getIndexHtml() {
  if (cachedIndexHtml) return cachedIndexHtml;
  const indexPath = path.join(webDist, "index.html");
  const raw = fs.readFileSync(indexPath, "utf8");
  const emb =
    process.env.HERMES_DASHBOARD_TUI === "1" ||
    ["1", "true", "yes"].includes(
      (process.env.HERMES_DASHBOARD_EMBEDDED_CHAT || "").toLowerCase(),
    )
      ? "true"
      : "false";
  const inj = `<script>window.__HERMES_SESSION_TOKEN__="${sessionToken}";window.__HERMES_DASHBOARD_EMBEDDED_CHAT__=${emb};</script>`;
  cachedIndexHtml = raw.replace(/<\/head>/i, `${inj}</head>`);
  return cachedIndexHtml;
}

async function main() {
  if (!fs.existsSync(path.join(webDist, "index.html"))) {
    console.error(
      "Falta web/dist (ejecuta `pnpm run build` en la raíz o `pnpm --dir web run build`).",
    );
    process.exit(1);
  }

  const childEnv = {
    ...process.env,
    HERMES_DASHBOARD_SESSION_TOKEN: sessionToken,
    HERMES_WEB_DIST: webDist,
  };

  const py = pythonExecutable();
  const child = spawn(
    py,
    [
      "-m",
      "uvicorn",
      "hermes_cli.web_server:app",
      "--host",
      "127.0.0.1",
      "--port",
      internalPort,
      "--log-level",
      process.env.UVICORN_LOG_LEVEL || "warning",
    ],
    {
      cwd: repoRoot,
      env: childEnv,
      stdio: "inherit",
    },
  );

  child.on("exit", (code, signal) => {
    if (signal === "SIGTERM" || signal === "SIGINT") process.exit(0);
    if (code && code !== 0) {
      console.error(`[stack] uvicorn terminó con código ${code}`);
      process.exit(code);
    }
  });

  await waitForBackend(internalTarget);

  const app = express();
  app.set("trust proxy", 1);

  const apiProxy = createProxyMiddleware(
    (pathname) =>
      pathname.startsWith("/api") || pathname.startsWith("/dashboard-plugins"),
    { target: internalTarget, changeOrigin: true, ws: true, logLevel: "warn" },
  );

  app.use(apiProxy);

  app.use(
    express.static(webDist, {
      index: false,
      fallthrough: true,
      maxAge: process.env.NODE_ENV === "production" ? "1h" : 0,
    }),
  );

  app.use((req, res, next) => {
    if (req.method !== "GET" && req.method !== "HEAD") return next();
    if (req.path.startsWith("/api") || req.path.startsWith("/dashboard-plugins")) return next();
    res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");
    res.type("html").send(getIndexHtml());
  });

  const server = http.createServer(app);
  server.on("upgrade", (req, socket, head) => {
    const p = req.url?.split("?")[0] || "";
    if (p.startsWith("/api") || p.startsWith("/dashboard-plugins")) {
      apiProxy.upgrade(req, socket, head);
    } else {
      socket.destroy();
    }
  });

  server.listen(listenPort, "0.0.0.0", () => {
    console.log(
      `[stack] Express en 0.0.0.0:${listenPort} → API FastAPI en ${internalTarget}`,
    );
  });

  const shutdown = () => {
    child.kill("SIGTERM");
    server.close(() => process.exit(0));
  };
  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
