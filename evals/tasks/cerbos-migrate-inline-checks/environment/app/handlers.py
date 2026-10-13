"""Invoice HTTP handlers."""

from flask import Blueprint, abort, g, jsonify, request

import flags
import store
from permissions import can

bp = Blueprint("invoices", __name__)


def _load_invoice(invoice_id):
    """Load an invoice the current user's tenant can see, or 404."""
    invoice = store.get_invoice(invoice_id)
    if invoice is None or invoice["tenant_id"] != g.user["tenant_id"]:
        # Never reveal that another tenant's invoice exists.
        abort(404)
    return invoice


def _amount_from_body():
    body = request.get_json(silent=True) or {}
    amount = body.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
        abort(400)
    return amount


@bp.get("/health")
def health():
    return jsonify(status="ok")


@bp.post("/invoices")
def create_invoice():
    if g.user["role"] not in ("manager", "accountant", "admin"):
        abort(403)
    amount = _amount_from_body()
    invoice_id, invoice = store.create_invoice(g.user["tenant_id"], g.user["id"], amount)
    return jsonify(id=invoice_id, **invoice), 201


@bp.get("/invoices/<invoice_id>")
def get_invoice(invoice_id):
    invoice = _load_invoice(invoice_id)
    if not can(g.user, "view", invoice):
        abort(403)
    tenant = store.get_tenant(g.user["tenant_id"])
    layout = "v2" if flags.is_enabled("pdf_layout_v2", tenant) else "v1"
    return jsonify(id=invoice_id, layout=layout, **invoice)


@bp.put("/invoices/<invoice_id>")
def update_invoice(invoice_id):
    invoice = _load_invoice(invoice_id)
    if not can(g.user, "edit", invoice):
        abort(403)
    invoice["amount"] = _amount_from_body()
    return jsonify(id=invoice_id, **invoice)


@bp.delete("/invoices/<invoice_id>")
def delete_invoice(invoice_id):
    invoice = _load_invoice(invoice_id)
    if not can(g.user, "delete", invoice):
        abort(403)
    store.delete_invoice(invoice_id)
    return "", 204


@bp.post("/invoices/<invoice_id>/approve")
def approve_invoice(invoice_id):
    invoice = _load_invoice(invoice_id)
    if g.user["role"] not in ("manager", "admin"):
        abort(403)
    if invoice["owner_id"] == g.user["id"]:
        abort(403)  # nobody approves their own invoice
    if invoice["amount"] > 10000 and g.user["role"] != "admin":
        abort(403)
    if invoice["status"] != "submitted":
        abort(409)
    invoice["status"] = "approved"
    return jsonify(id=invoice_id, **invoice)


@bp.get("/invoices/<invoice_id>/export")
def export_invoice(invoice_id):
    invoice = _load_invoice(invoice_id)
    tenant = store.get_tenant(g.user["tenant_id"])
    if not flags.is_enabled("csv_export", tenant):
        abort(403)
    if g.user["role"] == "viewer":
        abort(403)
    csv = "id,tenant_id,owner_id,amount,status\n"
    csv += f"{invoice_id},{invoice['tenant_id']},{invoice['owner_id']},{invoice['amount']},{invoice['status']}\n"
    return csv, 200, {"Content-Type": "text/csv"}
