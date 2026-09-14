#!/usr/bin/env bash
# Build the PyPI source tarball and wheel into dist/.
#
# Usage:
#   ./build.sh
#   PYTHON=/path/to/python ./build.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ -z "${PYTHON:-}" ]; then
  if [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
  else
    PYTHON=python
  fi
fi

echo "==> Using $($PYTHON -c 'import sys; print(sys.executable, sys.version.split()[0])')"

install_build_deps() {
  "$PYTHON" -m pip install -U build setuptools wheel
}

if ! install_build_deps; then
  echo "==> pip is managed by the OS; creating a local virtualenv"
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    "$PYTHON" -m venv "$ROOT/.venv"
  fi
  PYTHON="$ROOT/.venv/bin/python"
  echo "==> Using $($PYTHON -c 'import sys; print(sys.executable, sys.version.split()[0])')"
  "$PYTHON" -m pip install -U pip build setuptools wheel
fi

rm -rf dist build src/*.egg-info *.egg-info

echo "==> Building sdist and wheel"
"$PYTHON" -m build --sdist --wheel

echo
echo "==> Artifacts"
ls -lh dist
echo
echo "Check, then upload:"
echo "  $PYTHON -m pip install twine"
echo "  $PYTHON -m twine check dist/*"
echo "  $PYTHON -m twine upload dist/*"
