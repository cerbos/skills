"""In-memory data store, loaded from the JSON file named by APP_DATA."""

import itertools
import json
import os
from pathlib import Path

DEFAULT_DATA = Path(__file__).parent / "data" / "seed.json"

_data = json.loads(Path(os.environ.get("APP_DATA", DEFAULT_DATA)).read_text())

TENANTS = _data["tenants"]
USERS = _data["users"]
INVOICES = _data["invoices"]

_ids = itertools.count(1)


def get_user(user_id):
    return USERS.get(user_id)


def get_tenant(tenant_id):
    return TENANTS.get(tenant_id)


def get_invoice(invoice_id):
    return INVOICES.get(invoice_id)


def create_invoice(tenant_id, owner_id, amount):
    invoice_id = f"inv-new-{next(_ids)}"
    INVOICES[invoice_id] = {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "amount": amount,
        "status": "draft",
    }
    return invoice_id, INVOICES[invoice_id]


def delete_invoice(invoice_id):
    INVOICES.pop(invoice_id, None)
