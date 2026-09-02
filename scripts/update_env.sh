#!/usr/bin/env bash
set -Eeuo pipefail

# Create or repair the project virtualenv and reinstall ibm-patchwatch.
#
# Usage:
#   ./scripts/update_env.sh
#   source ./scripts/update_env.sh          # update + keep venv active
#   ./scripts/update_env.sh --recreate
#   ./scripts/update_env.sh --test
#
# Optional:
#   PYTHON_BIN=/usr/bin/python3.12 ./scripts/update_env.sh

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
VENV_DIR="${REPO_ROOT}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FORCE_RECREATE=0
RUN_TESTS=0

usage() {
    cat <<'EOF'
Usage: scripts/update_env.sh [options]

Options:
  --recreate   Recreate .venv even when it looks healthy
  --test       Run pytest after updating, if pytest is installed
  -h, --help   Show this help

If the script is sourced, the resulting virtualenv remains active:
  source scripts/update_env.sh
EOF
}

for arg in "$@"; do
    case "$arg" in
        --recreate) FORCE_RECREATE=1 ;;
        --test) RUN_TESTS=1 ;;
        -h|--help) usage; return 0 2>/dev/null || exit 0 ;;
        *)
            echo "ERROR: unknown option: $arg" >&2
            usage >&2
            return 2 2>/dev/null || exit 2
            ;;
    esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERROR: Python executable not found: $PYTHON_BIN" >&2
    return 1 2>/dev/null || exit 1
fi

if ! "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
    echo "ERROR: ibm-patchwatch requires Python >= 3.11" >&2
    "$PYTHON_BIN" --version >&2 || true
    return 1 2>/dev/null || exit 1
fi

recreate_reason=""

if (( FORCE_RECREATE )); then
    recreate_reason="requested with --recreate"
elif [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    recreate_reason=".venv is missing or incomplete"
else
    # A moved/copied venv can contain valid-looking files whose absolute
    # prefixes/shebangs still point to the old repository path.
    actual_prefix="$(${VENV_DIR}/bin/python -c 'import os,sys; print(os.path.realpath(sys.prefix))' 2>/dev/null || true)"
    expected_prefix="$(cd -- "${VENV_DIR}" 2>/dev/null && pwd -P || true)"
    if [[ -z "$actual_prefix" || "$actual_prefix" != "$expected_prefix" ]]; then
        recreate_reason=".venv points to a different location"
    elif [[ -f "${VENV_DIR}/bin/ibm-patchwatch" ]]; then
        current_shebang="$(head -n 1 "${VENV_DIR}/bin/ibm-patchwatch" 2>/dev/null || true)"
        expected_shebang="#!${VENV_DIR}/bin/python"
        if [[ "$current_shebang" != "$expected_shebang" ]]; then
            recreate_reason="ibm-patchwatch entry point contains a stale path"
        fi
    fi
fi

if [[ -n "$recreate_reason" ]]; then
    echo "[env] Recreating ${VENV_DIR} (${recreate_reason})"

    # If an old/moved venv is active, remove its influence before rebuilding.
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        unset VIRTUAL_ENV || true
        hash -r 2>/dev/null || true
    fi

    rm -rf -- "${VENV_DIR}"
    "$PYTHON_BIN" -m venv "${VENV_DIR}"
else
    echo "[env] Existing virtualenv is healthy: ${VENV_DIR}"
fi

VENV_PYTHON="${VENV_DIR}/bin/python"

echo "[env] Python: $(${VENV_PYTHON} --version 2>&1)"
echo "[env] Installing/updating ibm-patchwatch in editable mode"
cd -- "$REPO_ROOT"
"${VENV_PYTHON}" -m pip install -e .

# Clear Bash's remembered command location. This matters after moving a repo
# or replacing a virtualenv.
hash -r 2>/dev/null || true

PATCHWATCH="${VENV_DIR}/bin/ibm-patchwatch"
if [[ ! -x "$PATCHWATCH" ]]; then
    echo "ERROR: installation completed but ${PATCHWATCH} was not created" >&2
    return 1 2>/dev/null || exit 1
fi

echo "[env] ibm-patchwatch: ${PATCHWATCH}"
"${PATCHWATCH}" --version

if (( RUN_TESTS )); then
    if "${VENV_PYTHON}" -c 'import pytest' >/dev/null 2>&1; then
        echo "[env] Running tests"
        "${VENV_PYTHON}" -m pytest
    else
        echo "[env] pytest is not installed; skipping tests"
    fi
fi

# When sourced, activate the environment in the caller shell. When executed,
# activation cannot persist, so print the exact command to use.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    hash -r 2>/dev/null || true
    echo "[env] Activated: ${VIRTUAL_ENV}"
else
    echo
    echo "Environment is ready. Activate it with:"
    echo "  source \"${VENV_DIR}/bin/activate\""
fi
