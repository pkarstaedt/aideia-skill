#!/usr/bin/env python3
"""Configure the native Codex or Hermes MCP entry after a read-only check."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import termios
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, TextIO

import tomlkit
import yaml

SUPPORTED_PROTOCOL_VERSIONS = {"2025-06-18", "2025-11-25"}
MAX_MCP_RESPONSE_BYTES = 1_048_576


class Terminal:
    """Use separate read/write streams because /dev/tty is not seekable."""

    def __init__(self, reader: TextIO, writer: TextIO, control_fd: int) -> None:
        self.reader = reader
        self.writer = writer
        self.control_fd = control_fd

    def isatty(self) -> bool:
        return self.reader.isatty() and self.writer.isatty()

    def readline(self) -> str:
        return self.reader.readline()

    def write(self, value: str) -> int:
        return self.writer.write(value)

    def flush(self) -> None:
        self.writer.flush()


def prompt(stream: TextIO, message: str, *, secret: bool = False) -> str:
    """Read setup values from the controlling terminal, including under curl|bash."""
    if not stream.isatty():
        raise RuntimeError("An interactive terminal is required; no configuration was changed.")
    if secret:
        reader = getattr(stream, "reader", sys.stdin)
        control_fd = getattr(stream, "control_fd", reader.fileno())
        old_settings = termios.tcgetattr(control_fd)
        hidden_settings = old_settings[:]
        hidden_settings[3] &= ~termios.ECHO
        termios.tcsetattr(control_fd, termios.TCSAFLUSH, hidden_settings)
        try:
            stream.write(message)
            stream.flush()
            value = reader.readline()
            if not value:
                raise RuntimeError("Input ended; no configuration was changed.")
            return value.rstrip("\r\n")
        finally:
            termios.tcsetattr(control_fd, termios.TCSAFLUSH, old_settings)
            stream.write("\n")
            stream.flush()
    print(message, end="", file=stream, flush=True)
    value = stream.readline()
    if not value:
        raise RuntimeError("Input ended; no configuration was changed.")
    return value.strip()


def https_url(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.fragment


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward a bearer token to a redirected origin."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _set_response_timeout(response: Any, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    # urllib's socket timeout is an inactivity timeout. Refresh it against one
    # deadline so an SSE heartbeat cannot keep setup alive indefinitely.
    stream = getattr(response, "fp", None)
    raw = getattr(stream, "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is not None:
        sock.settimeout(remaining)


def _read_response(response: Any, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < MAX_MCP_RESPONSE_BYTES:
        _set_response_timeout(response, deadline)
        chunk = response.read(min(65536, MAX_MCP_RESPONSE_BYTES - len(data)))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
    raise RuntimeError("MCP discovery response exceeded the size limit.")


def _read_sse_response(response: Any, deadline: float, request_id: int | None) -> dict[str, Any]:
    line = bytearray()
    data_lines: list[bytes] = []
    total = 0
    while total < MAX_MCP_RESPONSE_BYTES:
        _set_response_timeout(response, deadline)
        byte = response.read(1)
        if not byte:
            break
        total += 1
        if byte != b"\n":
            line.extend(byte)
            continue
        current = bytes(line).removesuffix(b"\r")
        line.clear()
        if current.startswith(b"data:"):
            data_lines.append(current[5:].lstrip())
        elif not current and data_lines:
            try:
                payload = json.loads(b"\n".join(data_lines))
            except json.JSONDecodeError:
                data_lines.clear()
                continue
            data_lines.clear()
            if isinstance(payload, dict) and payload.get("jsonrpc") == "2.0" and payload.get("id") == request_id:
                return payload
    if total >= MAX_MCP_RESPONSE_BYTES:
        raise RuntimeError("MCP discovery response exceeded the size limit.")
    raise RuntimeError("MCP discovery returned an unexpected event stream.")


def mcp_call(url: str, token: str, method: str, params: dict[str, Any], request_id: int | None, timeout: int, protocol: str | None = None) -> dict[str, Any] | None:
    body: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
    if request_id is not None:
        body["id"] = request_id
    data = json.dumps(body, separators=(",", ":")).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if protocol:
        headers["MCP-Protocol-Version"] = protocol
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    deadline = time.monotonic() + timeout
    try:
        with opener.open(request, timeout=max(0.001, deadline - time.monotonic())) as response:
            if method.startswith("notifications/"):
                return None
            if response.headers.get_content_type() == "text/event-stream":
                return _read_sse_response(response, deadline, request_id)
            raw = _read_response(response, deadline)
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()
        raise RuntimeError("MCP connection check failed (TLS, network, or server error).") from None
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict) and payload.get("jsonrpc") == "2.0" and payload.get("id") == request_id:
            return payload
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    # Streamable HTTP permits a single JSON-RPC result in an SSE response.
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if line.startswith("data:"):
            try:
                payload = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("jsonrpc") == "2.0" and payload.get("id") == request_id:
                return payload
    raise RuntimeError("MCP discovery returned an unexpected response.")


def check_mcp(url: str, token: str) -> list[dict[str, Any]]:
    initialized = mcp_call(
        url,
        token,
        "initialize",
        {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "aideia-setup", "version": "0.1.0"}},
        1,
        20,
    )
    if initialized is None or initialized.get("error") or not isinstance(initialized.get("result"), dict):
        raise RuntimeError("MCP initialization failed. Check the URL, token, and External agents status.")
    protocol = initialized["result"].get("protocolVersion")
    if protocol not in SUPPORTED_PROTOCOL_VERSIONS:
        raise RuntimeError("MCP initialization returned an unsupported protocol version.")
    mcp_call(url, token, "notifications/initialized", {}, None, 20, protocol)
    result = mcp_call(url, token, "tools/list", {}, 2, 60, protocol)
    if result is None or result.get("error"):
        raise RuntimeError("MCP tool discovery failed. Check External agents and service availability.")
    tools = result.get("result", {}).get("tools") if isinstance(result.get("result"), dict) else None
    if not isinstance(tools, list) or any(not isinstance(tool, dict) for tool in tools):
        raise RuntimeError("MCP tool discovery returned an invalid tool list.")
    return tools


def config_path(client: str) -> Path:
    if client == "codex":
        return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "config.yaml"


def read_config(path: Path, client: str) -> tuple[Any, bytes]:
    original = path.read_bytes() if path.exists() else b""
    try:
        text = original.decode("utf-8")
        if client == "codex":
            config: Any = tomlkit.parse(text)
        else:
            config = yaml.safe_load(text) if text.strip() else {}
            if config is None:
                config = {}
    except (tomlkit.exceptions.ParseError, yaml.YAMLError, UnicodeDecodeError):
        # Parser diagnostics may quote nearby configuration values, including secrets.
        raise ValueError(f"{client.title()} configuration is malformed; it was not changed.") from None
    if not isinstance(config, dict):
        raise TypeError(f"{client.title()} configuration root must be a mapping.")
    return config, original


def set_server(config: Any, client: str, url: str, token: str) -> None:
    servers = config.get("mcp_servers")
    if servers is None:
        servers = tomlkit.table() if client == "codex" else {}
        config["mcp_servers"] = servers
    if not isinstance(servers, dict):
        raise TypeError("mcp_servers must be a mapping; configuration was not changed.")
    if client == "codex":
        entry = tomlkit.table()
        entry["url"] = url
        entry["http_headers"] = {"Authorization": f"Bearer {token}"}
        entry["startup_timeout_sec"] = 20
        entry["tool_timeout_sec"] = 60
    else:
        entry = {
            "url": url,
            "headers": {"Authorization": f"Bearer {token}"},
            "connect_timeout": 20,
            "timeout": 60,
            "supports_parallel_tool_calls": False,
        }
    servers["aideia"] = entry


def write_config(path: Path, client: str, config: Any, original: bytes) -> None:
    text = tomlkit.dumps(config) if client == "codex" else yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(f"{path.name}.aideia-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.bak")
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def client_choices() -> tuple[list[str], dict[str, str]]:
    found: dict[str, str] = {}
    for client in ("codex", "hermes"):
        executable = shutil.which(client)
        if executable:
            try:
                version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5, check=False)
                lines = (version.stdout or version.stderr).strip().splitlines()
                found[client] = lines[0][:120] if lines else "version unavailable"
            except (OSError, subprocess.TimeoutExpired):
                found[client] = "version unavailable"
    return list(found), found


def install_skill(client: str, manifest: dict[str, Any], repo_root: Path, terminal: TextIO) -> None:
    channels = manifest.get("codex", {}) if client == "codex" else manifest.get("hermes", {})
    if not channels or not any(channels.values()):
        print(f"Optional {client.title()} skill installation is not published yet; MCP setup remains available.")
        return
    required = ("marketplace_source", "marketplace_name", "plugin_id") if client == "codex" else ("skill_url",)
    if any(not isinstance(channels.get(key), str) or not channels[key] for key in required):
        print(f"The {client.title()} skill channel is incomplete; MCP remains configured and skill installation was skipped.")
        return
    answer = prompt(terminal, "Install the optional Aideia skill? [y/N] ").lower()
    if answer not in ("y", "yes"):
        print(f"Skipped the optional {client.title()} skill; MCP remains configured.")
        return
    if client == "codex":
        source = channels["marketplace_source"]
        marketplace = channels["marketplace_name"]
        plugin = channels["plugin_id"]
        try:
            listed = subprocess.run(["codex", "plugin", "list", "--json"], capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            print("Could not safely check installed Codex plugins; MCP remains configured and skill installation was skipped.")
            return
        try:
            installed = json.loads(listed.stdout)["installed"] if listed.returncode == 0 else None
        except (json.JSONDecodeError, KeyError, TypeError):
            installed = None
        if not isinstance(installed, list):
            print("Could not safely check installed Codex plugins; MCP remains configured and skill installation was skipped.")
            return
        existing = [entry for entry in installed if isinstance(entry, dict) and (entry.get("name") == "aideia" or entry.get("pluginId") == plugin)]
        for entry in existing:
            old_plugin = entry.get("pluginId", "aideia")
            old_marketplace = entry.get("marketplaceName")
            if not old_marketplace or prompt(terminal, "An Aideia Codex plugin exists. Replace it? [y/N] ").lower() not in ("y", "yes"):
                print("Skipped the existing Codex plugin; MCP remains configured.")
                return
            removed = subprocess.run(["codex", "plugin", "remove", f"{old_plugin}@{old_marketplace}"], capture_output=True, text=True, timeout=60, check=False)
            if removed.returncode:
                print("Could not replace the existing Codex plugin; MCP remains configured.")
                return
        commands = (["codex", "plugin", "marketplace", "add", source], ["codex", "plugin", "add", f"{plugin}@{marketplace}"])
    else:
        url = channels["skill_url"]
        try:
            listed = subprocess.run(["hermes", "skills", "list"], capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            print("Could not safely check installed Hermes skills; MCP remains configured and skill installation was skipped.")
            return
        if listed.returncode:
            print("Could not safely check installed Hermes skills; MCP remains configured and skill installation was skipped.")
            return
        exists = any(line.strip().split()[0].lower() == "aideia" for line in listed.stdout.splitlines() if line.strip())
        if exists and prompt(terminal, "An Aideia skill exists. Replace it? [y/N] ").lower() not in ("y", "yes"):
            print("Skipped the existing Hermes skill; MCP remains configured.")
            return
        commands = ("hermes", "skills", "install", url, *( ["--force"] if exists else [])),
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired):
            print(f"Optional {client.title()} skill installation failed; MCP remains configured.")
            return
        if result.returncode:
            print(f"Optional {client.title()} skill installation failed; MCP remains configured.")
            return
    print(f"Installed the optional {client.title()} skill. Start a new session to load it.")


def run(args: argparse.Namespace, terminal: TextIO) -> int:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Guided setup supports Linux only; use the manual client instructions.")
    repo_root = Path(args.repo_root).resolve()
    candidates, versions = client_choices()
    if args.client:
        if args.client not in candidates:
            raise RuntimeError(f"{args.client} is not installed or was not found on PATH.")
        selected = [args.client]
    else:
        if not candidates:
            raise RuntimeError("Install Codex CLI or Hermes first, then rerun setup.")
        print("Installed clients:")
        for index, client in enumerate(candidates, 1):
            print(f"  {index}. {client.title()} ({versions[client]}) — {config_path(client)}")
        if len(candidates) == 1:
            selected = candidates
        else:
            choice = prompt(terminal, "Choose Codex, Hermes, or both [1/2/b]: ").lower()
            if choice not in ("1", "2", "b", "both"):
                raise RuntimeError("No client selected; no configuration was changed.")
            selected = candidates if choice in ("b", "both") else [candidates[int(choice) - 1]]
    print("Setup will validate your token with a read-only initialize and tools/list request.")
    url = prompt(terminal, "Paste the HTTPS MCP server URL shown in Aideia: ")
    if not https_url(url):
        raise RuntimeError("Enter a valid HTTPS URL without embedded credentials or a fragment.")
    tokens: dict[str, str] = {}
    if len(selected) == 2:
        shared = prompt(terminal, "Use the same token for both clients? [Y/n] ").lower() in ("", "y", "yes")
    else:
        shared = True
    first_token = prompt(terminal, "Paste your Aideia access token (input hidden): ", secret=True)
    if not first_token or "\n" in first_token or "\r" in first_token:
        raise RuntimeError("A non-empty single-line token is required.")
    tokens[selected[0]] = first_token
    for client in selected[1:]:
        if shared:
            tokens[client] = first_token
        else:
            tokens[client] = prompt(terminal, f"Paste the {client.title()} token (input hidden): ", secret=True)
            if not tokens[client] or "\n" in tokens[client] or "\r" in tokens[client]:
                raise RuntimeError("A non-empty single-line token is required.")
    tool_counts: dict[str, int] = {}
    for client, token in tokens.items():
        while True:
            try:
                tool_counts[client] = len(check_mcp(url, token))
                break
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                print("Check that the token is active and External agents is enabled. No client file has been changed.")
                if prompt(terminal, "Retry the read-only connection check? [y/N] ").lower() not in ("y", "yes"):
                    raise RuntimeError("Setup canceled before any client file was changed.") from None
    print(f"Connection authenticated for all selected clients; {tool_counts[selected[0]]} tools are available (no tools were called).")
    manifest = json.loads((repo_root / "distribution.json").read_text(encoding="utf-8"))
    pending: list[tuple[str, Path, Any, bytes]] = []
    for client in selected:
        path = config_path(client)
        print(f"{client.title()} configuration: {path}")
        config, original = read_config(path, client)
        servers = config.get("mcp_servers", {})
        if "aideia" in servers and prompt(terminal, "Replace the existing Aideia MCP entry and its credentials? [y/N] ").lower() not in ("y", "yes"):
            print(f"Skipped {client.title()}; existing configuration is unchanged.")
            continue
        pending.append((client, path, config, original))
    for client, path, config, original in pending:
        token = tokens[client]
        set_server(config, client, url, token)
        write_config(path, client, config, original)
        verified, _ = read_config(path, client)
        entry = verified["mcp_servers"]["aideia"]
        auth = entry.get("http_headers", entry.get("headers", {})).get("Authorization")
        if entry.get("url") != url or auth != f"Bearer {token}":
            raise RuntimeError(f"Could not verify {client.title()} configuration at {path}.")
        os.chmod(path, 0o600)
        print(f"Configured {client.title()} with owner-only permissions at {path}.")
        install_skill(client, manifest, repo_root, terminal)
        print(f"Start a new {client.title()} session to discover Aideia tools.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--client", choices=("codex", "hermes"))
    args = parser.parse_args()
    try:
        with open("/dev/tty", "r", encoding="utf-8") as reader, open("/dev/tty", "w", encoding="utf-8") as writer:
            control_fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
            try:
                return run(args, Terminal(reader, writer, control_fd))
            finally:
                os.close(control_fd)
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        # Exception text is deliberately sanitized; never print urllib/body details.
        print(f"Aideia setup stopped ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        if exc.filename == "/dev/tty":
            print("Aideia setup needs a terminal for hidden token entry; no configuration was changed.", file=sys.stderr)
            return 1
        print("Aideia setup stopped because a local file or command could not be accessed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
