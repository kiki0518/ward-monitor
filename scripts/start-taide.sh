#!/bin/bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$project_dir/backend/taide.env.local" ]]; then
  source "$project_dir/backend/taide.env.local"
fi
server_path="${LLAMA_SERVER:-$project_dir/.runtime/llama.cpp/build/bin/llama-server}"
model_path="${1:-${TAIDE_MODEL_PATH:-}}"
if [[ ! -x "$server_path" ]]; then
  echo "找不到 llama-server，請在 backend/taide.env.local 設定 LLAMA_SERVER。" >&2
  exit 1
fi
if [[ -z "$model_path" || ! -f "$model_path" ]]; then
  echo "找不到 TAIDE GGUF 模型。請設定 TAIDE_MODEL_PATH，或執行 bash scripts/start-taide.sh /完整路徑/model.gguf。" >&2
  exit 1
fi
if [[ "$(head -c 4 "$model_path")" != "GGUF" ]]; then
  echo "模型不是有效的 GGUF 檔案，請確認下載已完成。" >&2
  exit 1
fi
exec "$server_path" -m "$model_path" --alias "${TAIDE_MODEL:-taide-handover}" \
  --host 127.0.0.1 --port "${TAIDE_PORT:-8080}" -c "${TAIDE_CONTEXT_SIZE:-2048}" --parallel 1 --batch-size 128 --ubatch-size 64 \
  --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on
