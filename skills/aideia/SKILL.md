---
name: aideia
description: Use a connected Aideia account to answer questions about personal records, current state, schedules, and historical patterns, or carry out requested journaling, activity, and reminder actions through its permitted MCP tools. Use when the user asks to work with their Aideia information; it does not configure or administer an Aideia deployment.
metadata:
  version: "0.1.0-dev"
---

# Aideia

Aideia maintains the connected user's personal records and assistant state. Use its MCP tools to work with those records and supported actions. This skill adds workflow guidance; the live tool descriptions and schemas define the actual capabilities and arguments.

## Use the connected interface

- Find the configured Aideia MCP connection using the client's available tool discovery mechanism. Tool names may have client-specific prefixes or aliases; identify them from their descriptions rather than constructing names.
- Inspect relevant live tool definitions before calling them. Use only exposed tools and permitted operations. The installed skill is not an authoritative tool inventory.
- If the connection is missing or authentication fails, explain the setup issue and refer the user to the Aideia connection settings or installation instructions. Do not search local files for credentials or ask the user to paste a token into chat.
- A tool can combine read and write operations. Availability of a read operation does not establish permission for a write.
- If access is denied, report the limitation. Do not switch accounts, use internal endpoints, or broaden permissions as a workaround. Let the user choose whether to change access in Aideia.
- External access does not include Aideia's internal memory tools. Do not substitute a private memory endpoint or another data source for an unavailable Aideia capability without the user's direction.

## Choose records that answer the question

Use current-state tools for live or current-day questions. Use closed-day historical records and rollups for past-day or period questions. A period summary can orient a review; a day-by-day question needs the relevant daily detail where available.

Use the dates, timezone, snapshot time, and coverage returned by Aideia. A sleep record's day may describe the morning it ended; preserve the tool's meaning rather than assigning a night from an unstated convention. Clarify a relative date only when the available user-local context does not resolve it.

Distinguish zero from missing, stale, partial, or unavailable data. An empty calendar result does not establish that the user is free when coverage is unknown. Report the supported scope instead of inventing absent detail.

Present observations separately from interpretations. Comparisons may suggest a pattern, but personal records alone do not establish what caused it. State relevant gaps and avoid claiming a health diagnosis or an outcome the records do not support.

## Make requested changes faithfully

Carry out the change the user requested using the permitted tool. Do not add unrelated records or actions. Ask for clarification when a material value is ambiguous; do not require a second confirmation for every ordinary action already clearly requested.

- Save journal text exactly as supplied for that purpose. Do not paraphrase, polish, or reconstruct it from earlier conversation. If the tool requires a capture reason or confirmation field, use the meaning in its live schema and do not fabricate confirmation.
- Resolve dates and times using the user's local context and the tool's documented defaults. Obtain missing timing when required for an activity or scheduled action; do not invent a placeholder time.
- For reminders and activities, preserve the user's intended content, timing, and scope. Do not add recurrence, change another reminder, or infer a completed activity without support.
- Check the returned tool result, including any error or partial-success status. Explain what was actually saved or accepted. A successful write does not establish that a separate provider sync or physical notification has completed.

## Handle errors without duplicating actions

Distinguish authentication, permission, validation, and execution failures using the structured information available. Correct invalid arguments only when the user's intent supplies the correction; otherwise ask for the missing detail.

A timeout or lost response after a write can leave its outcome unknown. Do not automatically repeat the mutation. If a permitted read can identify the resulting record reliably, use it to check; otherwise explain the uncertainty before considering another write. A transport failure is not proof of rollback.

Avoid repeated read attempts against an unavailable service. State what could and could not be retrieved rather than filling gaps from assumptions.

## Workflow examples

Read [references/workflows.md](references/workflows.md) when reviewing sleep or activity, comparing days, capturing journal text, or managing reminders. It provides use cases and interpretation guidance, not a duplicate tool schema.
