#!/bin/bash
# Reproducible CPU build for Intel Macs; output stays outside tracked source.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$project_dir/.runtime/llama.cpp"
if [[ ! -f "$source_dir/CMakeLists.txt" ]]; then
  git clone --depth 1 --branch b11057 https://github.com/ggml-org/llama.cpp.git "$source_dir"
fi
cmake -S "$source_dir" -B "$source_dir/build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DGGML_METAL=OFF -DGGML_OPENMP=OFF \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF
cmake --build "$source_dir/build" --target llama-server --parallel 4
"$source_dir/build/bin/llama-server" --version
