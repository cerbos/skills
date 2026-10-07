# Expenses API

FastAPI service for expense reports. Start it from this directory:

    uvicorn main:app --host 127.0.0.1 --port 8000

| Endpoint | Purpose |
| --- | --- |
| `GET /expenses/{id}` | View a report |
| `POST /expenses/{id}/approve` | Approve a report |
| `DELETE /expenses/{id}` | Delete a report (204) |

Callers are authenticated by the API gateway, which forwards the user ID in the
`X-User-Id` header. `store.py` loads users and reports from the JSON file named
by `EXPENSE_DATA` (default `data/seed.json`).

Users carry `roles`, `department`, `region` and, for managers, an
`approval_limit`. Reports carry `employee_id` (who filed it), `department`,
`region`, `amount` and `status` (`draft`, `submitted` or `approved`).
