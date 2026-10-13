"""Cerbos policy enforcement point for the invoice service."""

import os
import threading

from cerbos.engine.v1 import engine_pb2
from cerbos.sdk.grpc.client import CerbosClient
from google.protobuf.struct_pb2 import Value

import store

_client = None
_lock = threading.Lock()


def client():
    global _client
    with _lock:
        if _client is None:
            _client = CerbosClient(os.environ.get("CERBOS_GRPC_ADDR", "localhost:3593"), tls_verify=False)
        return _client


def _value(value):
    if isinstance(value, bool):
        return Value(bool_value=value)
    if isinstance(value, (int, float)):
        return Value(number_value=value)
    return Value(string_value=str(value))


def _attrs(values):
    return {key: _value(value) for key, value in values.items() if value is not None}


def principal(user):
    tenant = store.get_tenant(user["tenant_id"]) or {}
    return engine_pb2.Principal(
        id=user["id"],
        roles=[user["role"]],
        attr=_attrs({"tenant_id": user["tenant_id"], "plan": tenant.get("plan"), "status": user.get("status")}),
    )


def invoice_resource(invoice_id, invoice):
    return engine_pb2.Resource(
        kind="invoice",
        id=invoice_id,
        attr=_attrs(
            {
                "tenant_id": invoice["tenant_id"],
                "owner_id": invoice["owner_id"],
                "amount": invoice["amount"],
                "status": invoice["status"],
            }
        ),
    )


def api_resource(path):
    return engine_pb2.Resource(kind="api", id=path)


def is_allowed(user, action, resource):
    """Ask the PDP; any failure denies."""
    try:
        return client().is_allowed(action, principal(user), resource)
    except Exception:  # noqa: BLE001 - fail closed when the PDP is unavailable
        return False
