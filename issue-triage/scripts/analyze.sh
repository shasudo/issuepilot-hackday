#!/usr/bin/env bash
# Thin wrapper: run a triage analysis from anywhere inside the repo.
set -euo pipefail
cd "$(dirname "$0")/../.."
exec uv run issuepilot analyze "$@"
