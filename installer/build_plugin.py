#!/usr/bin/env python3
"""Stage a Codex skills-only plugin from the maintained skill source."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


def build(repo_root: Path, output: Path, version: str) -> Path:
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version):
        raise ValueError("version must be a semantic version")
    source = repo_root / "skills" / "aideia"
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError("maintained skills/aideia/SKILL.md was not found")
    package = output / "aideia"
    if package.exists():
        raise FileExistsError("output already contains an aideia plugin package; choose an empty output directory")
    (package / "skills").mkdir(parents=True)
    manifest = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "aideia",
        "version": version,
        "description": "Guidance for using Aideia MCP tools with care.",
        "author": {"name": "Aideia"},
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": "Aideia",
                    "shortDescription": "Use your Aideia records",
                    "longDescription": "Use the connected Aideia account to interpret personal records and carry out requested changes through permitted MCP tools.",
                    "developerName": "Aideia",
                    "category": "Productivity",
                    "capabilities": [],
                    "defaultPrompt": "Use my connected Aideia account to help with my request.",
                }
            }
        },
    }
    (package / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(source, package / "skills" / "aideia")
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(build(args.repo_root.resolve(), args.output.resolve(), args.version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
