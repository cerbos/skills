"""In-memory user directory and expense reports, loaded from a JSON file.

The file named by EXPENSE_DATA (default: data/seed.json next to this module)
holds {"users": [...], "expenses": [...]}. Writes stay in memory.
"""

import json
import os
import threading
from pathlib import Path

DATA_FILE = Path(
    os.environ.get("EXPENSE_DATA", Path(__file__).with_name("data") / "seed.json")
)


class Store:
    def __init__(self, path: Path = DATA_FILE):
        data = json.loads(Path(path).read_text())
        self.users = {user["id"]: user for user in data["users"]}
        self.expenses = {expense["id"]: expense for expense in data["expenses"]}
        self.lock = threading.Lock()

    def user(self, user_id: str) -> dict | None:
        return self.users.get(user_id)

    def expense(self, expense_id: str) -> dict | None:
        return self.expenses.get(expense_id)

    def approve(self, expense_id: str, approver_id: str) -> dict:
        with self.lock:
            expense = self.expenses[expense_id]
            expense["status"] = "approved"
            expense["approved_by"] = approver_id
            return expense

    def delete(self, expense_id: str) -> None:
        with self.lock:
            self.expenses.pop(expense_id, None)


store = Store()
