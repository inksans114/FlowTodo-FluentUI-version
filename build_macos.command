#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ "${1:-}" == "--check" ]]; then
    exec "${PYTHON_EXE:-python3}" tools/build_macos.py --check
fi
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
    echo "This build requires an Apple Silicon Mac. Use GitHub Actions on Windows."
    exit 1
fi
"${PYTHON_EXE:-python3.12}" -m venv .venv-macos
.venv-macos/bin/python -m pip install --upgrade pip
.venv-macos/bin/python -m pip install -r requirements-macos.txt
.venv-macos/bin/python tools/prepare_supervision_models.py
exec .venv-macos/bin/python tools/build_macos.py
