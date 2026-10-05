"""Start and stop a real PDP and the agent's app, and talk to the app over HTTP."""

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

LOGS = Path("/logs/verifier")
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PROXY_VARS = {"http_proxy", "https_proxy", "all_proxy", "grpc_proxy", "no_proxy"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def clean_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k.lower() not in PROXY_VARS}
    env.update({"NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
    env.update(extra)
    return env


def wait_for(url: str, process: subprocess.Popen, seconds: float, ok) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{process.args[0]} exited during startup: {process.returncode}")
        try:
            with HTTP.open(url, timeout=1) as response:
                if ok(response):
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"{url} did not become ready within {seconds} seconds")


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class PDP:
    def __init__(self, policies: Path, name: str = "pdp", audit: Path | None = None):
        self.http_port, self.grpc_port = free_port(), free_port()
        self.http_url = f"http://127.0.0.1:{self.http_port}"
        self.grpc_addr = f"127.0.0.1:{self.grpc_port}"
        config = {
            "server": {
                "httpListenAddr": f"127.0.0.1:{self.http_port}",
                "grpcListenAddr": f"127.0.0.1:{self.grpc_port}",
            },
            "storage": {"driver": "disk", "disk": {"directory": str(policies), "watchForChanges": False}},
        }
        if audit is not None:
            config["audit"] = {
                "enabled": True,
                "accessLogsEnabled": False,
                "decisionLogsEnabled": True,
                "backend": "file",
                "file": {"path": str(audit)},
            }
        self.config_path = LOGS / f"{name}-config.json"
        self.config_path.write_text(json.dumps(config, indent=2) + "\n")
        self.log_path = LOGS / f"{name}.log"
        self.process = None

    def start(self) -> None:
        log = self.log_path.open("a")
        self.process = subprocess.Popen(
            ["cerbos", "server", "--config", str(self.config_path), "--debug-listen-addr=127.0.0.1:0"],
            stdout=log,
            stderr=subprocess.STDOUT,
            env=clean_env(),
        )
        wait_for(
            f"{self.http_url}/_cerbos/health?service=cerbos.svc.v1.CerbosService",
            self.process,
            20,
            lambda r: json.load(r).get("status") == "SERVING",
        )

    def stop(self) -> None:
        stop(self.process)


class App:
    def __init__(self, workdir: Path, env: dict, name: str = "app"):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.workdir, self.env = workdir, env
        self.log_path = LOGS / f"{name}.log"
        self.process = None

    def start(self, health: str = "/health") -> None:
        log = self.log_path.open("a")
        self.process = subprocess.Popen(
            ["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=self.workdir,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=clean_env(**self.env),
        )
        wait_for(f"{self.base}{health}", self.process, 30, lambda r: r.status == 200)

    def stop(self) -> None:
        stop(self.process)

    def call(self, method: str, path: str, user: str | None = None, timeout: float = 10):
        """Return (status, parsed JSON body or text); status None on timeout/connection error."""
        headers = {"X-User-Id": user} if user is not None else {}
        request = urllib.request.Request(f"{self.base}{path}", method=method, headers=headers)
        try:
            with HTTP.open(request, timeout=timeout) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            return None, f"{type(error).__name__}: {error}"
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            return status, raw.decode(errors="replace")
