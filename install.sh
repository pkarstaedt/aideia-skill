#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a complete snapshot even when Bash receives this file on stdin.
# Resolve main once, then keep setup.py, dependencies, and metadata on that commit.
main() {
  if [[ "$(uname -s)" != Linux ]]; then
    printf '%s\n' 'Guided setup supports Linux only; use the manual client instructions.' >&2
    return 1
  fi
  if ! ( : </dev/tty ) 2>/dev/null; then
    printf '%s\n' 'Aideia setup needs a terminal for hidden token entry; no configuration was changed.' >&2
    return 1
  fi
  local dependency
  for dependency in curl tar python3; do
    command -v "$dependency" >/dev/null || {
      printf 'Install %s, then rerun Aideia setup.\n' "$dependency" >&2
      return 1
    }
  done

  local source_ref
  aideia_bootstrap_tmp="$(mktemp -d)"
  trap 'rm -rf -- "$aideia_bootstrap_tmp"' EXIT
  curl -fsSL https://api.github.com/repos/pkarstaedt/aideia-skill/commits/main -o "$aideia_bootstrap_tmp/revision.json"
  source_ref="$(python3 - "$aideia_bootstrap_tmp/revision.json" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    revision = json.load(stream).get("sha", "")
if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
    raise SystemExit("Could not resolve the Aideia installer source revision.")
print(revision)
PY
  )"
  printf 'Downloading Aideia setup (%s)...\n' "${source_ref:0:12}"
  curl -fsSL "https://github.com/pkarstaedt/aideia-skill/archive/$source_ref.tar.gz" -o "$aideia_bootstrap_tmp/source.tar.gz"
  mkdir "$aideia_bootstrap_tmp/source"
  tar -xzf "$aideia_bootstrap_tmp/source.tar.gz" --strip-components=1 -C "$aideia_bootstrap_tmp/source"
  bash "$aideia_bootstrap_tmp/source/setup.sh" --source-ref "$source_ref" "$@"
}

# Keep temporary-file cleanup local to the downloaded installer process.
( main "$@" )
