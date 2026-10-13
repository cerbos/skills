# Only list the expense reports each user may see

Our expenses API in `/workspace/app` (FastAPI and SQLAlchemy over SQLite, see
its `README.md`) has a `GET /expenses` endpoint that currently returns every
report in the database to anyone. The security team has written who may see
which reports as Cerbos policies in `/workspace/policies` (resource kind
`expense_report`, action `view`, version `default`). Those policies are
reviewed and correct; do not change them.

Make `GET /expenses` return only the reports the caller is allowed to view
according to our Cerbos PDP. The `status` filter, the `limit`/`offset` paging
(ordered by ID) and `total` must keep working and stay correct for each user:
`total` counts every report that user may see and that matches the filter. The
reports table can grow large, so the authorization filtering has to scale with
it. If the app cannot get an answer from the PDP, it must not return reports.
Use the official Cerbos Python SDK; it and every other package the app may need
are already installed, and nothing can be installed from the network.

Keep the rest of the app's contract: the `X-User-Id` header and 401 for
unknown users, the response shape, the database schema in `db.py`, and reading
the database from `DATABASE_URL`. Our test harness points `DATABASE_URL` at its
own database of users and reports, so decisions must come from the data rather
than from anything specific to the sample database.

Environment facts:

- In production the PDP runs next to the app. Read its address from the
  environment: `CERBOS_GRPC_ADDR` (gRPC, default `localhost:3593`) or
  `CERBOS_HTTP_ADDR` (HTTP, default `http://localhost:3592`). The connection is
  plaintext on localhost.
- The app is started from `/workspace/app` with
  `uvicorn main:app --host 127.0.0.1 --port <port>`; keep that working.
- Cerbos 0.55.0 is installed natively in this sandbox (`cerbos` on the PATH).
  Docker is unavailable. You can run a local PDP over the policies with
  `cerbos server --set=storage.disk.directory=/workspace/policies` while you
  work, but stop anything you start before you finish.
