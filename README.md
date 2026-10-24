# Aideia for your AI agent

Use your Aideia information with Codex or Hermes: review your day, explore recent patterns, save journal entries, and set reminders through the tools you choose to enable.

Aideia's MCP connection gives your agent access to those tools. The optional **Aideia skill** adds workflows and best practices for using them together.

## Get connected

You need an Aideia account and Codex or Hermes installed on your machine.

1. In Aideia's Preferences, enable **External agents** in the Aideia integrations area.
2. Open **External agents** under Apps and choose the tools and operations your agent can use.
3. Create an access token and copy the MCP server URL.
4. Configure that URL and bearer token in your agent, then install the skill if you want the additional guidance.

Aideia hosts the MCP server. On a headless machine, you can create the token from another device and configure the connection without opening a browser on the agent's machine.

### Guided Linux setup

The guided Linux installer is implemented for Codex CLI and Hermes, but there is not yet an immutable release. The development branch intentionally refuses to accept a token. A versioned release will provide this command:

```bash
curl -fsSL "<VERSIONED_SETUP_SCRIPT_URL>" | bash
```

Do not replace the placeholder with a `main` branch URL. The release command will download the installer implementation and distribution metadata from the same versioned source. Codex or Hermes and Python 3 with its `venv` module must already be installed; the installer does not install system packages. It asks for the HTTPS MCP URL and reads the token from a hidden terminal prompt. It checks authentication and tool discovery without calling tools before saving a connection.

Configuration is stored in the selected client's local config file with owner-only permissions. The optional Aideia skill is installed only when that release provides a verified client distribution channel. A skill installation problem does not remove a working MCP connection.

## Install the skill separately

If your MCP connection is already configured, you can add the skill independently. No stable Codex plugin or versioned Hermes skill entrypoint is published yet.

**Codex:** use the skills-only plugin when its release channel is published. It adds guidance and does not add a second MCP connection.

```text
Plugin installation instructions will be added with the verified release.
```

**Hermes:** install the versioned skill entrypoint when it is published:

```bash
<VERSIONED_HERMES_SKILL_URL>
```

The command will be `hermes skills install <VERSIONED_HERMES_SKILL_URL>`. Start a new agent session after installation. You can use the MCP tools without installing the skill.

## Try it

Ask your agent to use Aideia for something you have enabled:

- “Show my most recent sleep information and tell me which day it covers.”
- “Compare my activity over the last three days. Point out any missing information.”
- “Save this as my journal entry: …”
- “Remind me to call the dentist tomorrow at 10.”

The skill helps the agent distinguish current state from historical records, preserve your exact journal text, and explain incomplete information. Available actions follow the permissions you set in Aideia.

## Manage access

Revoke a token in the External agents app to disconnect an installation. Disable External agents to pause all external access. Keep your token private; it belongs in your agent's connection settings, not in the skill files.

## Explore the skill

- [Skill instructions](skills/aideia/SKILL.md)
- [Workflow examples](skills/aideia/references/workflows.md)
- [Download source ZIP](https://github.com/pkarstaedt/aideia-skill/archive/refs/heads/main.zip) — the development source is in `skills/aideia/`.

Tool names, arguments, and descriptions come from the live MCP connection. The workflow guidance here complements that interface.

## Release status

Current source version: `0.1.0-dev`. No stable installer or skill distribution is published. The setup implementation lives in `installer/setup.py`; `distribution.json` deliberately leaves release and client identifiers empty until matching artifacts have been tested. Do not run a main-branch installer with a real token.

Before publishing the website instructions, supply and verify the immutable release tag, the versioned setup-script URL, the Codex marketplace source/name/plugin identifier, the Hermes skill URL, and the screenshot assets for the two Aideia setup steps. Confirm the public website path and domain with its owner. Until then the installer command and skill download controls remain unavailable.
