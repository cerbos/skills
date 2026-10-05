# Expenses API

FastAPI service over SQLite with SQLAlchemy. Start it from this directory:

    uvicorn main:app --host 127.0.0.1 --port 8000

`python seed.py` recreates the sample database. `DATABASE_URL` selects the
database (default `sqlite:///data/expenses.db` next to `db.py`).

| Endpoint | Purpose |
| --- | --- |
| `GET /expenses?status=&limit=&offset=` | Page through expense reports, ordered by ID. Returns `{"items": [...], "total": N}`, where `total` counts every matching report, not just this page. |

Callers are authenticated by the API gateway, which forwards the user ID in the
`X-User-Id` header; unknown users get 401. Users live in the `users` table
(`roles` is comma-separated) and reports in `expenses` — see `db.py`.
