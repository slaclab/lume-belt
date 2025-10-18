#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------
# Execute tracked notebooks under docs/examples/,
# with optional --exclude patterns.
#
# Usage:
#   scripts/execute_notebooks.bash
#   scripts/execute_notebooks.bash --exclude "docs/examples/skip_this.ipynb,docs/examples/tmp_*.ipynb"
#
# Notes:
# - Patterns use shell-style globs (matched with [[ "$file" == $pattern ]])
# - Default skip pattern: "devel" (kept from your original script)
# -----------------------------------------------

# Parse optional --exclude arg (comma-separated)
EXCLUDE_PATTERNS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --exclude)
      IFS=',' read -r -a EXCLUDE_PATTERNS <<< "${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT/docs/examples/" || exit 1

# Collect tracked notebooks
NOTEBOOKS=$(git ls-files "*.ipynb")

# Keep your original default skip logic
SKIP_PATTERNS=("devel")

# Silence JupyterLab warning
export PYDEVD_DISABLE_FILE_VALIDATION=1

# Helper: should we skip this file?
should_skip() {
  local file="$1"

  # 1) user-provided exclude patterns
  for pat in "${EXCLUDE_PATTERNS[@]}"; do
    # Allow both absolute and repo-relative usage;
    # here we compare against the path relative to docs/examples/
    if [[ "$file" == $pat ]]; then
      return 0
    fi
  done

  # 2) original substring patterns (e.g., "devel")
  for pat in "${SKIP_PATTERNS[@]}"; do
    if [[ "$file" == *"$pat"* ]]; then
      return 0
    fi
  done

  return 1
}

# Nothing to do?
if [[ -z "${NOTEBOOKS}" ]]; then
  echo "No tracked .ipynb files under docs/examples/"
  exit 0
fi

# Execute
while IFS= read -r file; do
  [[ -z "$file" ]] && continue

  if should_skip "$file"; then
    echo "* Skipping: $(basename "$file") (matches an exclude/skip pattern)"
    echo
    continue
  fi

  pushd "$(dirname "$file")" > /dev/null || exit
  echo "* Processing: $(basename "$file") in $PWD"
  jupyter nbconvert \
    --to notebook \
    --execute "$(basename "$file")" \
    --inplace
  popd > /dev/null || exit
  echo
done <<< "$NOTEBOOKS"
