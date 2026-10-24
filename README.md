# Aideia skill

Portable guidance for agents using a connected Aideia account through MCP.

**Status:** initial content draft (`0.1.0-dev`). `install.sh` is a non-installing placeholder for the separate installer implementation. This repository does not yet contain a working installer, a Codex plugin package, or a verified fresh-device setup. No stable release has been published.

## Contents

```text
skills/aideia/
├── SKILL.md
├── references/workflows.md
└── agents/openai.yaml
```

`SKILL.md` is the entrypoint. It explains when to use Aideia and how to interpret records or make requested changes. The workflow reference provides examples for sleep and activity reviews, daily comparisons, schedules, journaling, and reminders. The optional Codex metadata supplies the skill's display information.

Live MCP descriptions and schemas remain authoritative for tool availability, arguments, and results. This repository deliberately does not maintain another tool catalog. The skill grants no access and contains no user credentials.

## Connection and distribution

Aideia hosts the MCP server. Clients need its external URL and an Aideia-issued token configured separately; they do not install or run the Aideia server locally.

The intended client scope is Codex and Hermes. OpenClaw packaging is deferred. Start from the same `skills/aideia/` directory when preparing client packages so workflow guidance has one maintained source. Use a release tag or commit to identify an exact source version rather than assuming that `main` is a stable release.

The current external-access design excludes internal memory tools. Other capabilities depend on what the Aideia platform exposes and what the user permits. Do not treat an example in this skill as a promise of access.

## Installer handoff

A separate implementation will replace the root `install.sh` placeholder at the same path. The stable download URL is:

https://raw.githubusercontent.com/pkarstaedt/aideia-skill/main/install.sh

The following command downloads the script and runs it with terminal input available for the eventual interactive prompts:

```bash
curl -fsSL https://raw.githubusercontent.com/pkarstaedt/aideia-skill/main/install.sh -o aideia-install.sh && bash aideia-install.sh
```

**Currently this exits with a message and a nonzero status without changing configuration.** It does not install anything or ask for a token. The URL follows `main` and is not a pinned stable release.

The actual installer is expected to configure the remote MCP connection for supported detected clients, prompt securely for the token, and offer installation of this skill.

For that implementation:

- The source skill directory is `skills/aideia/`; install the entire directory, including its relative workflow reference. Keep the installed folder name `aideia` consistent with the frontmatter.
- Use the user's actual external MCP URL. Do not invent a deployment hostname or package a private development endpoint.
- Keep credentials in the client's supported secret configuration, outside the skill and repository. Do not print or commit the token.
- Keep existing client configuration intact and avoid duplicate Aideia connections or duplicate skill registrations when rerun.
- Codex plugin packaging and the installer can use this same source skill without maintaining a second copy by hand.

These points describe the handoff; they do not implement or claim installer behavior.

## Direct links

- [Skill entrypoint](https://github.com/pkarstaedt/aideia-skill/blob/main/skills/aideia/SKILL.md)
- [Raw skill entrypoint](https://raw.githubusercontent.com/pkarstaedt/aideia-skill/main/skills/aideia/SKILL.md)
- [Download repository source ZIP](https://github.com/pkarstaedt/aideia-skill/archive/refs/heads/main.zip) — the skill is inside `skills/aideia/`; this is not a skill-only release archive.
- [Installer script](https://raw.githubusercontent.com/pkarstaedt/aideia-skill/main/install.sh) — placeholder until implementation is complete.

## Verification status

The initial content is checked for skill format and relative references. This does not establish whether the guidance is effective in a live agent session.

The requested fresh-device target is a **Linux headless machine**. A complete check remains pending until the installer and an authenticated external MCP endpoint are available. It needs to establish that the client detects the installed skill, resolves its supporting reference, connects using its configured token, and completes an authorized task. Keep write checks to explicitly requested disposable data.

Public distribution is still a draft. Repository publication does not imply marketplace approval, a working download service, or tested compatibility with every client version.
