"""Cerbos query-plan filtering for the expenses API."""

import os

from cerbos.engine.v1 import engine_pb2
from cerbos.sdk.grpc.client import CerbosClient
from cerbos_sqlalchemy import get_query
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Value
from sqlalchemy import Select

from db import Expense, User

CERBOS_ADDR = os.environ.get("CERBOS_GRPC_ADDR", "localhost:3593")

# One client (one gRPC channel) per process, plaintext on localhost.
client = CerbosClient(CERBOS_ADDR, tls_verify=False, timeout_secs=2)

# Every resource attribute the expense_report policy can mention, mapped to its column.
ATTR_MAP = {
    "request.resource.attr.owner": Expense.owner_id,
    "request.resource.attr.department": Expense.department,
    "request.resource.attr.region": Expense.region,
    "request.resource.attr.amount": Expense.amount,
    "request.resource.attr.status": Expense.status,
    "request.resource.attr.archived": Expense.archived,
}


def principal_for(user: User) -> engine_pb2.Principal:
    """Map a row from the users table onto a Cerbos principal."""
    attrs = {"department": user.department, "region": user.region, "review_threshold": user.review_threshold}
    return engine_pb2.Principal(
        id=user.id,
        roles=[role.strip() for role in user.roles.split(",") if role.strip()],
        attr={key: ParseDict(value, Value()) for key, value in attrs.items() if value is not None},
    )


def viewable_expenses(user: User) -> Select:
    """A SELECT over the reports this user may view. PDP errors propagate."""
    plan = client.plan_resources(
        "view", principal_for(user), engine_pb2.PlanResourcesInput.Resource(kind="expense_report")
    )
    # get_query handles ALWAYS_ALLOWED (no predicate), ALWAYS_DENIED (WHERE false)
    # and CONDITIONAL (translated predicate), raising on unmapped attributes.
    return get_query(plan, Expense, ATTR_MAP)
