"""Expense report API.

Run from this directory: uvicorn main:app --host 127.0.0.1 --port 8000
The API gateway authenticates callers and forwards the user ID in X-User-Id.
"""

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from authz import viewable_expenses
from db import Expense, User, get_session

app = FastAPI(title="Expenses")


def current_user(
    x_user_id: str | None = Header(default=None), session: Session = Depends(get_session)
) -> User:
    user = session.get(User, x_user_id) if x_user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="unknown user")
    return user


def serialize(expense: Expense) -> dict:
    return {
        "id": expense.id,
        "owner_id": expense.owner_id,
        "department": expense.department,
        "region": expense.region,
        "amount": expense.amount,
        "status": expense.status,
        "archived": expense.archived,
        "description": expense.description,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/expenses")
def list_expenses(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Expense reports the caller may see, ordered by ID, one page at a time."""
    try:
        query = viewable_expenses(user)
    except Exception as error:
        raise HTTPException(status_code=503, detail="authorization unavailable") from error
    if status is not None:
        query = query.where(Expense.status == status)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.order_by(Expense.id).limit(limit).offset(offset)).all()
    return {"items": [serialize(row) for row in rows], "total": total}
