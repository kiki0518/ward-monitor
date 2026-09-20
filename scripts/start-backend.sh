#!/bin/bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$project_dir/backend/taide.env.example"
if [[ -f "$project_dir/backend/taide.env.local" ]]; then
  source "$project_dir/backend/taide.env.local"
fi
cd "$project_dir/backend"
exec "$project_dir/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8000}"
