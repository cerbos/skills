"""Check independent authorization cases against fresh normal and strict PDPs."""

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

POLICIES = Path("/workspace/policies")
LOGS = Path("/logs/verifier")
CASES = Path("/tests/cases.json")
# Loopback requests must not be routed through a provider/proxy configuration.
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def addresses() -> tuple[str, str]:
    with socket.socket() as http, socket.socket() as grpc:
        http.bind(("127.0.0.1", 0))
        grpc.bind(("127.0.0.1", 0))
        return (
            f"127.0.0.1:{http.getsockname()[1]}",
            f"127.0.0.1:{grpc.getsockname()[1]}",
        )


def wait_ready(process: subprocess.Popen, base_url: str) -> None:
    deadline = time.monotonic() + 20
    url = f"{base_url}/_cerbos/health?service=cerbos.svc.v1.CerbosService"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"PDP exited during startup: {process.returncode}")
        try:
            with HTTP.open(url, timeout=1) as response:
                if json.load(response).get("status") == "SERVING":
                    return
        except (urllib.error.URLError, TimeoutError):
            # Startup can briefly refuse connections or return not-serving.
            time.sleep(0.1)
    raise RuntimeError("PDP did not become ready within 20 seconds")


def check_case(base_url: str, suite: dict, case: dict, mode: str) -> dict:
    principal = suite["principals"][case["principal"]]
    resource = {"policyVersion": "default", **suite["resources"][case["resource"]]}
    request = {
        "requestId": f"{mode}:{case['name']}",
        "principal": principal,
        "resources": [{"resource": resource, "actions": list(case["expected"])}],
    }
    record = {
        "mode": mode,
        "case": case["name"],
        "request": request,
        "expected": case["expected"],
        "passed": False,
    }
    http_request = urllib.request.Request(
        f"{base_url}/api/check/resources",
        data=json.dumps(request).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with HTTP.open(http_request, timeout=5) as response:
            body = json.load(response)
        record["response"] = body
        results = body.get("results", [])
        if body.get("requestId") != request["requestId"] or len(results) != 1:
            record["error"] = "Unexpected request ID or result count"
        else:
            result = results[0]
            actual_resource = result.get("resource", {})
            record["passed"] = (
                actual_resource.get("id") == resource["id"]
                and actual_resource.get("kind") == resource["kind"]
                and result.get("actions") == case["expected"]
                and not result.get("validationErrors")
            )
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        record["error"] = str(error)
    print(
        f"{'PASS' if record['passed'] else 'FAIL'}: {mode} CheckResources {case['name']}"
    )
    return record


@contextmanager
def pdp(strict: bool = False):
    """Start an isolated PDP, yield its HTTP address, and always stop it."""
    LOGS.mkdir(parents=True, exist_ok=True)
    mode = "strict" if strict else "normal"
    http_addr, grpc_addr = addresses()
    config = {
        "server": {"httpListenAddr": http_addr, "grpcListenAddr": grpc_addr},
        "storage": {
            "driver": "disk",
            "disk": {"directory": str(POLICIES), "watchForChanges": False},
        },
        "engine": {"strictEvaluation": strict},
    }
    config_path = LOGS / f"pdp-{mode}-config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    with (LOGS / f"pdp-{mode}.log").open("a") as log:
        process = subprocess.Popen(
            [
                "cerbos",
                "server",
                "--config",
                str(config_path),
                "--debug-listen-addr=127.0.0.1:0",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            base_url = f"http://{http_addr}"
            wait_ready(process, base_url)
            yield base_url
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def run_mode(suite: dict, strict: bool, records: list) -> None:
    mode = "strict" if strict else "normal"
    with pdp(strict=strict) as base_url:
        for case in suite["cases"]:
            records.append(check_case(base_url, suite, case, mode))


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    suite = json.loads(CASES.read_text())
    if not suite["cases"]:
        raise RuntimeError("CheckResources suite has no cases")
    records = []
    try:
        for strict in (False, True):
            run_mode(suite, strict, records)
    finally:
        (LOGS / "check-resources.json").write_text(json.dumps(records, indent=2) + "\n")
    if len(records) != 2 * len(suite["cases"]) or not all(r["passed"] for r in records):
        raise SystemExit("Live CheckResources decisions did not match the contract")


if __name__ == "__main__":
    main()
