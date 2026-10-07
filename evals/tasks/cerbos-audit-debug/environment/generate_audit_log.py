"""Regenerate environment/audit.log from the real PDP and the seeded (buggy) app.

Run inside the task image so the entries come from Cerbos 0.55.0 itself:

    docker build -t cerbos-audit-debug environment
    docker run --rm -v "$PWD/environment:/out" cerbos-audit-debug \
        python /out/generate_audit_log.py /out/audit.log

The image is not changed by this script; it only writes the log file.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt

OUT = Path(sys.argv[1])
LOG = Path("/var/log/cerbos/audit.log")
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SECRET = "dev-only-invoice-secret"

USERS = {
    "sam.patel": {"roles": ["employee"], "department": "Engineering"},
    "lee.wong": {"roles": ["employee"], "department": "IT"},
    "maria.garcia": {
        "roles": ["manager"],
        "department": "Engineering",
        "managed_cost_centers": ["CC-100", "CC-200"],
        "approval_limit": 5000,
    },
    "raj.mehta": {
        "roles": ["manager"],
        "department": "IT",
        "managed_cost_centers": ["CC-200", "CC-300"],
        "approval_limit": 25000,
    },
}

REQUESTS = [
    ("sam.patel", "GET", "INV-2041"),
    ("lee.wong", "GET", "INV-2043"),
    ("maria.garcia", "GET", "INV-2041"),
    ("maria.garcia", "POST", "INV-2041"),
    ("maria.garcia", "POST", "INV-2041"),
    ("raj.mehta", "GET", "INV-2043"),
    ("raj.mehta", "POST", "INV-2043"),
    ("sam.patel", "GET", "INV-2042"),
    ("maria.garcia", "POST", "INV-2043"),
    ("raj.mehta", "POST", "INV-2046"),
    ("lee.wong", "GET", "INV-2041"),
    ("raj.mehta", "POST", "INV-2044"),
    ("sam.patel", "POST", "INV-2041"),
    ("maria.garcia", "GET", "INV-2045"),
]


def wait(url: str) -> None:
    for _ in range(100):
        try:
            with HTTP.open(url, timeout=1):
                return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise SystemExit(f"{url} not ready")


def main() -> None:
    LOG.unlink(missing_ok=True)
    pdp = subprocess.Popen(["cerbos", "server", "--config", "/workspace/cerbos/config.yaml"])
    app = subprocess.Popen([sys.executable, "/workspace/app/app.py"], env={**os.environ})
    try:
        wait("http://127.0.0.1:3592/_cerbos/health")
        wait("http://127.0.0.1:8000/healthz")
        for user, method, invoice in REQUESTS:
            token = jwt.encode({"sub": user, "aud": "invoices", **USERS[user]}, SECRET, algorithm="HS256")
            path = f"/invoices/{invoice}" + ("/approve" if method == "POST" else "")
            request = urllib.request.Request(
                f"http://127.0.0.1:8000{path}",
                method=method,
                headers={"Authorization": f"Bearer {token}"},
                data=b"" if method == "POST" else None,
            )
            try:
                with HTTP.open(request, timeout=5) as response:
                    status = response.status
            except urllib.error.HTTPError as error:
                status = error.code
            print(user, method, path, status)
            time.sleep(0.3)
        time.sleep(1)
    finally:
        app.terminate()
        pdp.terminate()
        app.wait()
        pdp.wait()
    OUT.write_text(LOG.read_text())
    print(f"wrote {OUT} ({len(LOG.read_text().splitlines())} entries)")


if __name__ == "__main__":
    main()
