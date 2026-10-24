#!/usr/bin/env bash
set -euo pipefail

# Keep the original public path as a compatibility entrypoint. Released web
# instructions should use the versioned setup.sh asset, not this source branch.
script_path="${BASH_SOURCE[0]:-}"
if [[ -n "$script_path" && -f "$script_path" ]]; then
  script_dir="$(cd -- "$(dirname -- "$script_path")" && pwd)"
  if [[ -f "$script_dir/setup.sh" ]]; then
    exec bash "$script_dir/setup.sh" "$@"
  fi
fi

printf '%s\n' \
  'This installer is not available from the development branch.' \
  'Use the versioned setup.sh command after an immutable release is published.' >&2
exit 1
