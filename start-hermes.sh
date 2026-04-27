#!/usr/bin/env bash
# Arranque local: Vite (web/) + Express (server/index.js) que levanta uvicorn (API real).
# Requiere: pnpm install en la raíz, Python/uv con extras [web] (p. ej. uv sync --extra web --extra pty).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if command -v pnpm >/dev/null 2>&1; then
  exec pnpm run dev:all
fi
if command -v npm >/dev/null 2>&1; then
  exec npm run dev:all
fi
echo "Instala Node.js y pnpm o npm, luego en la raíz: pnpm install" >&2
exit 1
