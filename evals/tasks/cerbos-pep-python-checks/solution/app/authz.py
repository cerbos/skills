"""Cerbos policy enforcement for the expenses API."""

import os

from cerbos.engine.v1 import engine_pb2
from cerbos.sdk.grpc.client import CerbosClient
from fastapi import HTTPException
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Value

CERBOS_ADDR = os.environ.get("CERBOS_GRPC_ADDR", "localhost:3593")

# One client (one gRPC channel) per process, plaintext on localhost.
client = CerbosClient(CERBOS_ADDR, tls_verify=False, timeout_secs=2)


def _value(value) -> Value:
    return ParseDict(value, Value())


def _attrs(values: dict) -> dict:
    return {key: _value(value) for key, value in values.items() if value is not None}


def principal_for(user: dict) -> engine_pb2.Principal:
    """Map a user from our directory onto a Cerbos principal."""
    return engine_pb2.Principal(
        id=user["id"],
        roles=user["roles"],
        attr=_attrs(
            {
                "department": user.get("department"),
                "region": user.get("region"),
                "approval_limit": user.get("approval_limit"),
            }
        ),
    )


def resource_for(expense: dict) -> engine_pb2.Resource:
    """Map an expense report onto the expense_report resource."""
    return engine_pb2.Resource(
        id=expense["id"],
        kind="expense_report",
        attr=_attrs(
            {
                "owner": expense.get("employee_id"),
                "department": expense.get("department"),
                "region": expense.get("region"),
                "amount": expense.get("amount"),
                "status": expense.get("status"),
            }
        ),
    )


def authorize(user: dict, action: str, expense: dict) -> None:
    """Raise 403 unless the PDP allows the action. PDP errors propagate as 5xx."""
    try:
        allowed = client.is_allowed(action, principal_for(user), resource_for(expense))
    except Exception as error:
        raise HTTPException(status_code=503, detail="authorization unavailable") from error
    if not allowed:
        raise HTTPException(status_code=403, detail="forbidden")
