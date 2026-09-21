#!/bin/sh
set -eu
cd "$(dirname "$0")"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
if command -v uv >/dev/null 2>&1; then
    exec uv run --frozen python -m builder build "$@"
elif [ -x .venv/bin/python ]; then
    exec .venv/bin/python -m builder build "$@"
else
    exec python3 -m builder build "$@"
fi
