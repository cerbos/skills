"""Invoice approval service.

GET  /invoices/<id>          view an invoice
POST /invoices/<id>/approve  approve a submitted invoice

Callers authenticate with `Authorization: Bearer <token>`, an HS256 token issued
by our identity gateway. Every request is authorized by the Cerbos PDP.
"""

import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import jwt
from cerbos.sdk.client import CerbosClient
from cerbos.sdk.model import Principal, Resource

PORT = int(os.environ.get("PORT", "8000"))
CERBOS_URL = os.environ.get("CERBOS_URL", "http://localhost:3592")
INVOICES_FILE = Path(os.environ.get("INVOICES_FILE", Path(__file__).parent / "data" / "invoices.json"))
JWT_SECRET = os.environ.get("APP_JWT_SECRET", "dev-only-invoice-secret")

log = logging.getLogger("invoices")


@dataclass
class Invoice:
    id: str
    owner: str
    cost_center: str
    amount: float
    status: str
    description: str

    def to_api(self) -> dict:
        """JSON shape returned to the web UI."""
        return {
            "id": self.id,
            "owner": self.owner,
            "costCenter": self.cost_center,
            "amount": self.amount,
            "status": self.status,
            "description": self.description,
        }


class InvoiceStore:
    def __init__(self, path: Path):
        rows = json.loads(path.read_text())
        self._invoices = {row["id"]: Invoice(**row) for row in rows}
        self._lock = threading.Lock()

    def get(self, invoice_id: str) -> Invoice | None:
        return self._invoices.get(invoice_id)

    def set_status(self, invoice_id: str, status: str) -> None:
        with self._lock:
            self._invoices[invoice_id].status = status


class AuthError(Exception):
    pass


def principal_from_token(header: str | None) -> Principal:
    if not header or not header.startswith("Bearer "):
        raise AuthError("missing bearer token")
    try:
        claims = jwt.decode(header[7:], JWT_SECRET, algorithms=["HS256"], audience="invoices")
    except jwt.PyJWTError as error:
        raise AuthError(str(error)) from error
    return Principal(
        id=claims["sub"],
        roles=set(claims.get("roles", [])),
        attr={
            "department": claims.get("department", ""),
            "managed_cost_centers": claims.get("managed_cost_centers", []),
            "approval_limit": claims.get("approval_limit", 0),
        },
    )


def invoice_resource(invoice: Invoice) -> Resource:
    # Reuse the API representation so the PDP sees the same fields as the UI.
    attr = {key: value for key, value in invoice.to_api().items() if key != "id"}
    return Resource(id=invoice.id, kind="invoice", attr=attr)


cerbos = CerbosClient(CERBOS_URL, raise_on_error=True, timeout_secs=5)
store = InvoiceStore(INVOICES_FILE)


def is_allowed(action: str, principal: Principal, invoice: Invoice) -> bool:
    return cerbos.is_allowed(action, principal, invoice_resource(invoice))


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _route(self, method: str) -> None:
        if method == "GET" and self.path == "/healthz":
            return self._send(200, {"status": "ok"})
        match = re.fullmatch(r"/invoices/([\w.-]+)(/approve)?", self.path)
        if not match or (method == "GET") == bool(match.group(2)):
            return self._send(404, {"error": "not found"})
        try:
            principal = principal_from_token(self.headers.get("Authorization"))
        except AuthError as error:
            return self._send(401, {"error": str(error)})
        invoice = store.get(match.group(1))
        if invoice is None:
            return self._send(404, {"error": "invoice not found"})
        action = "approve" if match.group(2) else "view"
        try:
            allowed = is_allowed(action, principal, invoice)
        except Exception:  # noqa: BLE001 - an unreachable PDP is an outage, not a denial
            log.exception("authorization check failed")
            return self._send(503, {"error": "authorization service unavailable"})
        if not allowed:
            log.info("denied %s %s for %s", action, invoice.id, principal.id)
            return self._send(403, {"error": "forbidden"})
        if action == "approve":
            store.set_status(invoice.id, "approved")
        return self._send(200, store.get(invoice.id).to_api())

    def do_GET(self) -> None:  # noqa: N802
        self._route("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._route("POST")

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s %s", self.address_string(), fmt % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info("invoice service on :%d, PDP at %s", PORT, CERBOS_URL)
    server.serve_forever()


if __name__ == "__main__":
    main()
