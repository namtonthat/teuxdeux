#!/usr/bin/env bash
#
# Set up teuxdeux for local development:
#   1. create a virtual environment
#   2. install the package (with dev extras) in editable mode
#   3. scaffold a .env from .env.example
#
# Re-running is safe — existing files are left untouched.

set -euo pipefail

# Resolve the project root (the parent of this script's directory).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!\033[0m  %s\n' "$1"; }

# --- 1 & 2: environment + install ------------------------------------------
if command -v uv >/dev/null 2>&1; then
  if [ -d ".venv" ]; then
    warn ".venv already exists — leaving it as-is"
  else
    info "Creating virtual environment with uv"
    uv venv
  fi
  info "Installing teuxdeux (editable, with dev extras)"
  uv pip install -e ".[dev]"
else
  warn "uv not found — falling back to python -m venv + pip"
  if [ ! -d ".venv" ]; then
    info "Creating virtual environment at .venv"
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  info "Installing teuxdeux (editable, with dev extras)"
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -e ".[dev]"
fi

# --- 3: .env scaffold ------------------------------------------------------
if [ -f ".env" ]; then
  warn ".env already exists — leaving it as-is"
else
  info "Creating .env from .env.example"
  cp .env.example .env
fi

cat <<'DONE'

Setup complete.

Next steps:
  1. Edit .env and add your TeuxDeux credentials.
  2. Activate the environment:
       source .venv/bin/activate
  3. Verify auth:
       teuxdeux user

DONE
