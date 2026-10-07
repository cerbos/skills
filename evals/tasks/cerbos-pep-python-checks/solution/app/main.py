"""Expense report API.

Run from this directory: uvicorn main:app --host 127.0.0.1 --port 8000
The API gateway authenticates callers and forwards the user ID in X-User-Id.
"""

from fastapi import Depends, FastAPI, Header, HTTPException, Response

from authz import authorize
from store import store

app = FastAPI(title="Expenses")


def current_user(x_user_id: str | None = Header(default=None)) -> dict:
    user = store.user(x_user_id) if x_user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="unknown user")
    return user


def load_expense(expense_id: str) -> dict:
    expense = store.expense(expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="expense report not found")
    return expense


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/expenses/{expense_id}")
def view_expense(expense_id: str, user: dict = Depends(current_user)) -> dict:
    expense = load_expense(expense_id)
    authorize(user, "view", expense)
    return expense


@app.post("/expenses/{expense_id}/approve")
def approve_expense(expense_id: str, user: dict = Depends(current_user)) -> dict:
    expense = load_expense(expense_id)
    authorize(user, "approve", expense)
    return store.approve(expense_id, user["id"])


@app.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: str, user: dict = Depends(current_user)) -> Response:
    expense = load_expense(expense_id)
    authorize(user, "delete", expense)
    store.delete(expense_id)
    return Response(status_code=204)
