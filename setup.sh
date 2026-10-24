#!/usr/bin/env bash
set -euo pipefail

# Release packaging sets this to the immutable release tag; development source stays inert.
AIDEIA_RELEASE_REF=""
script_path="${BASH_SOURCE[0]:-}"
repo_root=""
if [[ -n "$script_path" && -f "$script_path" ]]; then
  candidate="$(cd -- "$(dirname -- "$script_path")" && pwd)"
  if [[ -f "$candidate/installer/setup.py" && -f "$candidate/distribution.json" ]]; then
    repo_root="$candidate"
  fi
fi

tmp_dir=""
cleanup() { [[ -z "$tmp_dir" ]] || rm -rf -- "$tmp_dir"; }
trap cleanup EXIT HUP INT TERM

if [[ -z "$repo_root" ]]; then
  if [[ ! "$AIDEIA_RELEASE_REF" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf '%s\n' \
      'Aideia guided setup is implemented, but no immutable release is published yet.' \
      'Do not enter a token from the development branch. Use the manual setup guide after a release is available.' >&2
    exit 1
  fi
  command -v curl >/dev/null || { printf '%s\n' 'Install curl, then rerun setup.' >&2; exit 1; }
  command -v tar >/dev/null || { printf '%s\n' 'Install tar, then rerun setup.' >&2; exit 1; }
  tmp_dir="$(mktemp -d)"
  curl -fsSL "https://github.com/pkarstaedt/aideia-skill/archive/refs/tags/$AIDEIA_RELEASE_REF.tar.gz" -o "$tmp_dir/source.tar.gz"
  mkdir "$tmp_dir/source"
  tar -xzf "$tmp_dir/source.tar.gz" --strip-components=1 -C "$tmp_dir/source"
  repo_root="$tmp_dir/source"
fi

if [[ ! "$AIDEIA_RELEASE_REF" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf '%s\n' 'This is development source, not a versioned installer release.' >&2
  exit 1
fi
command -v python3 >/dev/null || { printf '%s\n' 'Install Python 3 with the venv module, then rerun setup.' >&2; exit 1; }
tmp_dir="${tmp_dir:-$(mktemp -d)}"
if ! python3 -m venv "$tmp_dir/venv" >/dev/null 2>&1; then
  printf '%s\n' 'Install Python 3 with the venv module (often python3-venv), then rerun setup.' >&2
  exit 1
fi
if ! "$tmp_dir/venv/bin/python" - "$repo_root/distribution.json" "$AIDEIA_RELEASE_REF" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as stream:
    raise SystemExit(0 if json.load(stream).get("release_ref") == sys.argv[2] else 1)
PY
then
  printf '%s\n' 'Installer and distribution metadata do not match the same release.' >&2
  exit 1
fi
"$tmp_dir/venv/bin/python" -m pip install --disable-pip-version-check --no-input -r "$repo_root/installer/requirements.lock" >/dev/null
"$tmp_dir/venv/bin/python" "$repo_root/installer/setup.py" --repo-root "$repo_root"
