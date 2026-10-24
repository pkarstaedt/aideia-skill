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

Run this command on the machine where Codex CLI or Hermes is installed:

```bash
curl -fsSL https://raw.githubusercontent.com/pkarstaedt/aideia-skill/main/install.sh | bash
```

Choose your installed client, paste the HTTPS MCP URL from Aideia, and enter your token at the hidden prompt. Setup checks the connection before saving it, preserves unrelated settings, and asks before replacing an existing Aideia connection. Your token is stored in the client's configuration with owner-only file permissions.

You need `curl`, `tar`, and Python 3 with its `venv` module. Setup uses a temporary Python environment for the TOML/YAML configuration readers and removes it afterwards. It does not require uv or install system packages.

The command downloads the current source and keeps its setup files on one Git commit. Start a new Codex or Hermes session after setup.

## Install the skill separately

The MCP connection works without the optional skill. Packaged skill channels are not published yet; you can install the current source directly:

**Codex:** ask its skill installer to install this directory:

```text
$skill-installer install https://github.com/pkarstaedt/aideia-skill/tree/main/skills/aideia
```

**Hermes:** install from the skill entrypoint:

```bash
hermes skills install https://raw.githubusercontent.com/pkarstaedt/aideia-skill/main/skills/aideia/SKILL.md
```

Start a new session to load the skill. These source URLs follow the current `main` branch.

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
