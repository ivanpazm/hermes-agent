#!/usr/bin/env node
/**
 * Copia la salida de Vite (web/dist) a hermes_cli/web_dist para que
 * setuptools (package-data) y `hermes dashboard` sigan encontrando el bundle.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const src = path.join(root, "web", "dist");
const dst = path.join(root, "hermes_cli", "web_dist");

if (!fs.existsSync(path.join(src, "index.html"))) {
  console.error("sync-web-dist: falta web/dist/index.html. Ejecuta antes: pnpm --dir web run build");
  process.exit(1);
}

fs.rmSync(dst, { recursive: true, force: true });
fs.mkdirSync(path.dirname(dst), { recursive: true });
fs.cpSync(src, dst, { recursive: true });
console.log("sync-web-dist: web/dist → hermes_cli/web_dist");
