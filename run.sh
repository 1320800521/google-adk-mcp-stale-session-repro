#!/usr/bin/env bash
set -euo pipefail

versions=("2.7.1" "2.8.0" "2.9.1")
for version in "${versions[@]}"; do
  echo "=== google-adk ${version} ==="
  uv run --no-project --with "google-adk[mcp]==${version}" python repro/repro.py
done
