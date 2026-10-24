import http.client
import importlib.util
import json
import os
import pty
import select
import ssl
import subprocess
import sys
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aideia_setup", ROOT / "installer" / "setup.py")
setup = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(setup)


class MCPHandler(BaseHTTPRequestHandler):
    requests: ClassVar[list] = []
    reject = False
    fail_tool_list = False
    use_sse = False
    mcp_version = "2025-11-25"
    heartbeat_forever = False
    keep_open_after_response = False

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.__class__.requests.append((body, self.headers.get("Authorization"), self.headers.get("MCP-Protocol-Version")))
        if self.__class__.reject or (self.__class__.fail_tool_list and body["method"] == "tools/list"):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"secret must never be shown")
            return
        if body["method"] == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        if body["method"] == "initialize":
            result = {"protocolVersion": self.__class__.mcp_version, "capabilities": {"tools": {}}, "serverInfo": {"name": "fixture", "version": "1"}}
        else:
            result = {"tools": []}
        payload = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result})
        if self.__class__.use_sse:
            response = f"event: message\ndata: {payload}\n\n".encode()
            content_type = "text/event-stream"
        else:
            response = payload.encode()
            content_type = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if not (self.__class__.use_sse and self.__class__.heartbeat_forever):
            self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        if self.__class__.use_sse and self.__class__.heartbeat_forever:
            while True:
                try:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    time.sleep(0.01)
                except (BrokenPipeError, ConnectionResetError):
                    return
        self.wfile.write(response)
        if self.__class__.use_sse and self.__class__.keep_open_after_response:
            while True:
                try:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    time.sleep(0.01)
                except (BrokenPipeError, ConnectionResetError):
                    return

    def log_message(self, *_args):
        pass


@pytest.fixture
def mcp_server(tmp_path, monkeypatch):
    cert = tmp_path / "server.pem"
    key = tmp_path / "server.key"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert), "-days", "1", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1", "-addext", "basicConstraints=critical,CA:TRUE"],
        check=True,
        capture_output=True,
    )
    server = HTTPServer(("127.0.0.1", 0), MCPHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Retain normal roots for dependency downloads while trusting the MCP fixture.
    trust = tmp_path / "trust.pem"
    roots = ssl.create_default_context().get_ca_certs(binary_form=True)
    trust.write_text("".join(ssl.DER_cert_to_PEM_cert(root) for root in roots) + cert.read_text())
    monkeypatch.setenv("SSL_CERT_FILE", str(trust))
    MCPHandler.requests = []
    MCPHandler.reject = False
    MCPHandler.fail_tool_list = False
    MCPHandler.use_sse = False
    MCPHandler.mcp_version = "2025-11-25"
    MCPHandler.heartbeat_forever = False
    MCPHandler.keep_open_after_response = False
    yield f"https://localhost:{server.server_port}/mcp"
    server.shutdown()
    thread.join(timeout=2)
    server.server_close()


def test_mcp_check_initializes_notifies_and_only_lists_tools(mcp_server):
    assert setup.check_mcp(mcp_server, "token-with-special-!@#$") == []
    assert [request[0]["method"] for request in MCPHandler.requests] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
    ]
    assert all(request[1] == "Bearer token-with-special-!@#$" for request in MCPHandler.requests)
    assert MCPHandler.requests[2][2] == "2025-11-25"


def test_mcp_sse_response_returns_matching_jsonrpc_message(mcp_server):
    MCPHandler.use_sse = True
    assert setup.check_mcp(mcp_server, "sse-token") == []


def test_sse_returns_matching_message_even_when_connection_stays_open(mcp_server):
    MCPHandler.use_sse = True
    MCPHandler.keep_open_after_response = True
    assert setup.mcp_call(mcp_server, "stream-token", "tools/list", {}, 2, 1, "2025-11-25") == {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"tools": []},
    }


def test_supported_legacy_protocol_version_is_accepted_and_forwarded(mcp_server):
    MCPHandler.mcp_version = "2025-06-18"
    assert setup.check_mcp(mcp_server, "legacy-token") == []
    assert MCPHandler.requests[2][2] == "2025-06-18"


def test_unsupported_negotiated_protocol_version_is_rejected(mcp_server):
    MCPHandler.mcp_version = "2099-01-01"
    with pytest.raises(RuntimeError, match="unsupported protocol version"):
        setup.check_mcp(mcp_server, "token")
    assert [request[0]["method"] for request in MCPHandler.requests] == ["initialize"]


def test_sse_heartbeats_cannot_extend_total_request_deadline(mcp_server):
    MCPHandler.use_sse = True
    MCPHandler.heartbeat_forever = True
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="MCP connection check failed"):
        setup.mcp_call(mcp_server, "heartbeat-token", "tools/list", {}, 2, 0.25, "2025-11-25")
    assert time.monotonic() - started < 1.0


def test_sse_response_size_is_bounded(mcp_server, monkeypatch):
    MCPHandler.use_sse = True
    monkeypatch.setattr(setup, "MAX_MCP_RESPONSE_BYTES", 12)
    with pytest.raises(RuntimeError, match="exceeded the size limit"):
        setup.mcp_call(mcp_server, "bounded-token", "tools/list", {}, 2, 5, "2025-11-25")


def test_malformed_http_failure_does_not_expose_token(monkeypatch):
    class BrokenOpener:
        def open(self, *_args, **_kwargs):
            raise http.client.BadStatusLine("bad token-secret-value")

    monkeypatch.setattr(setup.urllib.request, "build_opener", lambda *_args: BrokenOpener())
    with pytest.raises(RuntimeError) as exc:
        setup.mcp_call("https://example.test/mcp", "token-secret-value", "ping", {}, 1, 1)
    assert "token-secret-value" not in str(exc.value)


def test_invalid_token_error_never_contains_response_body(mcp_server):
    MCPHandler.reject = True
    with pytest.raises(RuntimeError, match="MCP connection check failed") as exc:
        setup.check_mcp(mcp_server, "do-not-print-me")
    assert "secret must never be shown" not in str(exc.value)
    assert "do-not-print-me" not in str(exc.value)


def test_tool_discovery_error_is_reported_without_calling_any_tool(mcp_server):
    MCPHandler.fail_tool_list = True
    with pytest.raises(RuntimeError, match="MCP connection check failed"):
        setup.check_mcp(mcp_server, "valid-token")
    assert [request[0]["method"] for request in MCPHandler.requests] == ["initialize", "notifications/initialized", "tools/list"]


@pytest.mark.parametrize("client", ["codex", "hermes"])
def test_merge_preserves_unrelated_config_and_secures_config_and_backup(tmp_path, client):
    path = tmp_path / ("config.toml" if client == "codex" else "config.yaml")
    original = b'# keep this note\n[other]\nvalue = "unchanged"\n' if client == "codex" else b"other:\n  value: unchanged\n"
    path.write_bytes(original)
    config, raw = setup.read_config(path, client)
    setup.set_server(config, client, "https://aideia.example/mcp", "token-special-!@#$")
    setup.write_config(path, client, config, raw)
    parsed, _ = setup.read_config(path, client)
    assert parsed["other"]["value"] == "unchanged"
    assert parsed["mcp_servers"]["aideia"]["url"] == "https://aideia.example/mcp"
    assert path.stat().st_mode & 0o777 == 0o600
    backup = next(tmp_path.glob(path.name + ".aideia-*.bak"))
    assert backup.read_bytes() == original
    assert backup.stat().st_mode & 0o777 == 0o600
    if client == "codex":
        assert "# keep this note" in path.read_text()
    else:
        assert parsed["mcp_servers"]["aideia"]["supports_parallel_tool_calls"] is False


@pytest.mark.parametrize(("client", "bad"), [("codex", b"bad = ["), ("hermes", b"other: [unterminated")])
def test_malformed_config_is_not_changed_or_backed_up(tmp_path, client, bad):
    path = tmp_path / ("config.toml" if client == "codex" else "config.yaml")
    path.write_bytes(bad)
    with pytest.raises(ValueError, match="configuration is malformed"):
        setup.read_config(path, client)
    assert path.read_bytes() == bad
    assert list(tmp_path.glob("*.bak")) == []


def test_bad_https_url_is_rejected():
    assert not setup.https_url("http://example.test/mcp")
    assert not setup.https_url("https://user:pass@example.test/mcp")
    assert not setup.https_url("https://example.test/mcp#fragment")
    assert setup.https_url("https://example.test/mcp")


def test_plugin_package_uses_maintained_skill_source(tmp_path):
    build_spec = importlib.util.spec_from_file_location("build_plugin", ROOT / "installer" / "build_plugin.py")
    build_plugin = importlib.util.module_from_spec(build_spec)
    assert build_spec.loader is not None
    build_spec.loader.exec_module(build_plugin)
    package = build_plugin.build(ROOT, tmp_path, "0.1.0")
    manifest = json.loads((package / "plugin.json").read_text())
    assert manifest["name"] == "aideia"
    assert not (package / "mcp.json").exists()
    assert (package / "skills/aideia/references/workflows.md").read_bytes() == (ROOT / "skills/aideia/references/workflows.md").read_bytes()
    assert len(manifest["extensions"]["com.openai"]["interface"]["shortDescription"]) <= 30
    with pytest.raises(FileExistsError, match="choose an empty output directory"):
        build_plugin.build(ROOT, tmp_path, "0.1.1")


def test_unreleased_script_refuses_to_run_from_a_piped_checkout():
    env = dict(os.environ)
    env.pop("AIDEIA_SETUP_TESTING", None)
    result = subprocess.run(["bash"], input=(ROOT / "setup.sh").read_text(), text=True, cwd=ROOT, env=env, capture_output=True, check=False)
    assert result.returncode != 0
    assert "no immutable release is published" in result.stderr


def run_interactive_setup(tmp_path, mcp_url, answers, home=None, *, command=None, extra_env=None):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_codex = fake_bin / "codex"
    fake_codex.write_text("#!/bin/sh\necho 'codex 1.2.3'\n")
    fake_codex.chmod(0o755)
    codex_home = home or tmp_path / "custom-codex"
    env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}", CODEX_HOME=str(codex_home))
    env.update(extra_env or {})
    pid, descriptor = pty.fork()
    if pid == 0:
        if command:
            os.execve("/bin/bash", ["bash", "-c", command], env)
        os.execve(sys.executable, [sys.executable, str(ROOT / "installer/setup.py"), "--repo-root", str(ROOT), "--client", "codex"], env)
    output = bytearray()
    pending = [
        (b"Paste the HTTPS MCP server URL", mcp_url.encode() + b"\n"),
        (b"Paste your Aideia access token", b"integration-token-!@#$\n"),
        *answers,
    ]
    deadline = time.monotonic() + 60
    status = None
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([descriptor], [], [], 0.2)
            if readable:
                try:
                    output.extend(os.read(descriptor, 4096))
                except OSError:
                        pass
            for prompt_text, answer in pending:
                if prompt_text in output:
                    os.write(descriptor, answer)
                    pending.remove((prompt_text, answer))
                    break
            waited, result = os.waitpid(pid, os.WNOHANG)
            if waited:
                status = result
                break
        if status is None:
            raise AssertionError(f"interactive setup timed out: {output.decode(errors='replace')}")
    finally:
        os.close(descriptor)
        if status is None:
            os.kill(pid, 15)
            os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), output.decode(errors="replace"), codex_home


def test_interactive_setup_uses_custom_home_hides_token_and_writes_mcp(mcp_server, tmp_path):
    result, output, codex_home = run_interactive_setup(tmp_path, mcp_server, [])
    config = codex_home / "config.toml"
    assert result == 0
    assert "integration-token-!@#$" not in output
    assert "Configured Codex with owner-only permissions" in output
    assert config.stat().st_mode & 0o777 == 0o600
    assert 'Authorization = "Bearer integration-token-!@#$"' in config.read_text()
    assert [request[0]["method"] for request in MCPHandler.requests] == ["initialize", "notifications/initialized", "tools/list"]


def test_interactive_setup_cancel_preserves_existing_config(mcp_server, tmp_path):
    fake_home = tmp_path / "custom-codex"
    fake_home.mkdir()
    config = fake_home / "config.toml"
    original = b"[other]\nvalue = 'preserve'\n\n[mcp_servers.aideia]\nurl = 'https://old.example/mcp'\n"
    config.write_bytes(original)
    (fake_home / "sentinel").write_text("unused")
    result, output, _ = run_interactive_setup(tmp_path / "child", mcp_server, [(b"Replace the existing Aideia MCP entry", b"n\n")], fake_home)
    assert result == 0
    assert "Skipped Codex" in output
    assert config.read_bytes() == original
    assert not list(fake_home.glob("*.bak"))


def test_interactive_invalid_token_cancel_leaves_config_missing(mcp_server, tmp_path):
    MCPHandler.reject = True
    result, output, codex_home = run_interactive_setup(
        tmp_path,
        mcp_server,
        [(b"Retry the read-only connection check", b"n\n")],
    )
    assert result != 0
    assert "No client file has been changed" in output
    assert not (codex_home / "config.toml").exists()
    assert "integration-token-!@#$" not in output


def test_client_paths_respect_custom_home(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-profile"))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-profile"))
    assert setup.config_path("codex") == tmp_path / "codex-profile/config.toml"
    assert setup.config_path("hermes") == tmp_path / "hermes-profile/config.yaml"


def test_client_version_with_empty_output_is_not_an_exception(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda client: "/usr/bin/codex" if client == "codex" else None)
    monkeypatch.setattr(setup.subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""))
    clients, versions = setup.client_choices()
    assert clients == ["codex"]
    assert versions["codex"] == "version unavailable"


def test_no_terminal_exits_before_discovery_or_configuration():
    result = subprocess.run(
        [sys.executable, str(ROOT / "installer/setup.py"), "--repo-root", str(ROOT)],
        input="",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "needs a terminal" in result.stderr


PUBLIC_INSTALL_COMMAND = "curl -fsSL https://raw.githubusercontent.com/pkarstaedt/aideia-skill/main/install.sh | bash"


@pytest.fixture
def installer_downloads(tmp_path):
    """Serve real source files through curl's download interface, pinned to one SHA."""
    archive = tmp_path / "source.tar.gz"
    revision = "a" * 40
    with tarfile.open(archive, "w:gz") as bundle:
        for relative in ["setup.sh", "installer/setup.py", "installer/requirements.lock", "distribution.json"]:
            bundle.add(ROOT / relative, arcname=f"aideia-skill-{revision}/{relative}")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python3").symlink_to(Path(sys.executable).resolve())
    curl = fake_bin / "curl"
    curl.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\nfrom pathlib import Path\n"
        f"root = Path({str(ROOT)!r})\narchive = Path({str(archive)!r})\n"
        "args = sys.argv[1:]\nurl = next(arg for arg in args if arg.startswith('https://'))\n"
        f"if url == 'https://api.github.com/repos/pkarstaedt/aideia-skill/commits/main': data = json.dumps({{'sha': {revision!r}}}).encode()\n"
        f"elif url == 'https://github.com/pkarstaedt/aideia-skill/archive/{revision}.tar.gz': data = archive.read_bytes()\n"
        "elif url == 'https://raw.githubusercontent.com/pkarstaedt/aideia-skill/main/install.sh': data = (root / 'install.sh').read_bytes()\n"
        "else: raise SystemExit(22)\n"
        "if '-o' in args: Path(args[args.index('-o') + 1]).write_bytes(data)\n"
        "else: sys.stdout.buffer.write(data)\n"
    )
    curl.chmod(0o755)
    hermes = fake_bin / "hermes"
    hermes.write_text("#!/bin/sh\necho 'Hermes fixture 1.0'\n")
    hermes.chmod(0o755)
    installer_temp = tmp_path / "installer-temp"
    installer_temp.mkdir()
    return {
        "HERMES_HOME": str(tmp_path / "custom-hermes"),
        "TMPDIR": str(installer_temp),
        "PIP_CACHE_DIR": str(tmp_path / "pip-cache"),
    }


@pytest.mark.parametrize("choice,clients", [(b"1\n", ["codex"]), (b"2\n", ["hermes"]), (b"b\n", ["codex", "hermes"])])
def test_public_pipe_installs_selected_clients(mcp_server, tmp_path, installer_downloads, choice, clients):
    answers = [(b"Choose Codex, Hermes, or both", choice)]
    if len(clients) == 2:
        answers.append((b"Use the same token for both", b"y\n"))
    result, output, codex_home = run_interactive_setup(
        tmp_path, mcp_server, answers, command=PUBLIC_INSTALL_COMMAND, extra_env=installer_downloads
    )
    assert result == 0, output
    assert "integration-token-!@#$" not in output
    for client in clients:
        path = codex_home / "config.toml" if client == "codex" else Path(installer_downloads["HERMES_HOME"]) / "config.yaml"
        config, _ = setup.read_config(path, client)
        entry = config["mcp_servers"]["aideia"]
        assert entry["url"] == mcp_server
        assert entry.get("http_headers", entry.get("headers"))["Authorization"] == "Bearer integration-token-!@#$"
        assert path.stat().st_mode & 0o777 == 0o600
    assert list(Path(installer_downloads["TMPDIR"]).iterdir()) == []
    assert [request[0]["method"] for request in MCPHandler.requests] == ["initialize", "notifications/initialized", "tools/list"] * len(clients)


def test_public_pipe_rejected_token_leaves_configs_unchanged(mcp_server, tmp_path, installer_downloads):
    MCPHandler.reject = True
    codex_home = tmp_path / "custom-codex"
    codex_home.mkdir()
    original = b"# Existing settings\nmodel = 'keep-me'\n"
    (codex_home / "config.toml").write_bytes(original)
    result, output, _ = run_interactive_setup(
        tmp_path, mcp_server,
        [(b"Choose Codex, Hermes, or both", b"1\n"), (b"Retry the read-only connection check", b"n\n")],
        command=PUBLIC_INSTALL_COMMAND, extra_env=installer_downloads,
    )
    assert result != 0
    assert "Setup canceled before any client file was changed" in output
    assert [request[0]["method"] for request in MCPHandler.requests] == ["initialize"]
    assert (codex_home / "config.toml").read_bytes() == original
    assert not list(codex_home.glob("*.bak"))
    assert "integration-token-!@#$" not in output
    assert list(Path(installer_downloads["TMPDIR"]).iterdir()) == []


def test_public_entrypoint_without_terminal_exits_before_downloads(tmp_path):
    result = subprocess.run(["bash"], input=(ROOT / "install.sh").read_text(), text=True, capture_output=True, start_new_session=True, check=False)
    assert result.returncode == 1
    assert "needs a terminal" in result.stderr
    assert "Downloading" not in result.stdout
