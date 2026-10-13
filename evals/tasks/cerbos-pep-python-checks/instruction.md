# Enforce expense report permissions with Cerbos

Our expenses API in `/workspace/app` (FastAPI, see its `README.md`) has no
authorization yet: any authenticated user can view, approve or delete any
expense report. The security team has written the access rules as Cerbos
policies in `/workspace/policies` (resource kind `expense_report`, version
`default`). Those policies are reviewed and correct; do not change them.

Wire the API up to our Cerbos PDP so that every endpoint enforces the policy
decision for its action (`view`, `approve`, `delete`) before doing anything.
A denied request must get HTTP 403 and must not change any data, and a
request the app cannot get a decision for must never succeed. Use the
official Cerbos Python SDK, which is already installed along with everything
else the app needs; nothing can be installed from the network.

Keep the rest of the app's contract as it is: the `X-User-Id` header and 401
for unknown users, 404 for reports that do not exist, the response bodies and
status codes of allowed requests, and loading users and reports from the file
named by `EXPENSE_DATA`. Our test harness swaps in its own users and reports
that way, so make sure decisions come from the attributes in that data rather
than from anything specific to the seed file.

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
