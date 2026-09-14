#!/usr/bin/env bash
# Build the PyPI source tarball and a wheel with a supported platform tag.
#
# Linux wheels from a plain `python -m build` are tagged linux_x86_64, which
# PyPI no longer accepts. This script runs auditwheel so the wheel is tagged
# manylinux_* (PEP 600) instead.
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

repair_linux_wheels() {
  local unrepaired repaired plat
  shopt -s nullglob
  unrepaired=(dist/*linux_*.whl)
  if [ ${#unrepaired[@]} -eq 0 ]; then
    return 0
  fi

  echo "==> Retagging Linux wheels with auditwheel (manylinux / musllinux)"
  if ! command -v patchelf >/dev/null 2>&1; then
    echo "error: patchelf is required to produce a PyPI-compatible Linux wheel" >&2
    echo "       install it (e.g. pacman -S patchelf / apt install patchelf) and retry" >&2
    return 1
  fi
  "$PYTHON" -m pip install -U auditwheel

  mkdir -p dist/repaired
  for whl in "${unrepaired[@]}"; do
    echo "    $(basename "$whl")"
    if ! "$PYTHON" -m auditwheel show "$whl"; then
      echo "error: auditwheel could not inspect $whl" >&2
      return 1
    fi
    if "$PYTHON" -m auditwheel repair --plat auto -w dist/repaired "$whl"; then
      rm -f "$whl"
      continue
    fi
    plat="$("$PYTHON" -m auditwheel show --only-plat "$whl" 2>/dev/null || true)"
    if [ -n "$plat" ] && [ "$plat" != "linux_x86_64" ] && [ "$plat" != "linux_i686" ]; then
      echo "    retrying with --plat $plat"
      "$PYTHON" -m auditwheel repair --plat "$plat" -w dist/repaired "$whl"
      rm -f "$whl"
      continue
    fi
    echo "error: $whl is tagged linux_* which PyPI rejects." >&2
    echo "       Build in a manylinux container (cibuildwheel) or install auditwheel/patchelf." >&2
    return 1
  done

  for repaired in dist/repaired/*.whl; do
    mv "$repaired" dist/
  done
  rmdir dist/repaired
}

case "$(uname -s)" in
  Linux) repair_linux_wheels ;;
esac

echo
echo "==> Artifacts"
ls -lh dist
echo
echo "Linux wheels must use a manylinux_* or musllinux_* platform tag."
echo "PyPI rejects linux_x86_64. See:"
echo "  https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/#platform-tag"
echo
echo "Check, then upload:"
echo "  $PYTHON -m pip install twine"
echo "  $PYTHON -m twine check dist/*"
echo "  $PYTHON -m twine upload dist/*"
