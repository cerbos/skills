# Move invoice authorization to Cerbos

Our invoice service in `/workspace/app` (Flask) has grown its permission logic
all over the code. We want Cerbos to be the one place that decides who may do
what, and we are cutting over directly: this is an internal service, and we have
agreed to skip a shadow period.

Please:

1. Write the Cerbos policies in `/workspace/policies`, with native test suites
   (`*_test.yaml`) showing both allowed and denied cases for each rule. Both of
   these must pass:

   ```sh
   cerbos compile /workspace/policies
   cerbos compile --strict-evaluation /workspace/policies
   ```

2. Change the app so that every authorization decision it makes today is made
   by the Cerbos PDP, and delete the old permission logic. No role checks
   should be left in the application code.

3. Keep behaviour exactly as it is. Every request, from every user, must get
   the same HTTP status code it gets today, including the 400, 401, 403, 404
   and 409 responses. If you find a rule that looks wrong, keep it as it is
   and mention it in your summary; we will change it separately.

Environment facts:

- Cerbos 0.55.0 is installed natively as `cerbos`; Docker is not available.
  Flask and the Cerbos Python SDK (`cerbos` 0.16.0) are already installed, and
  there is no network access for installing packages.
- The service is started from `/workspace` with `python /workspace/app/server.py`.
  It reads `PORT`, and `APP_DATA`, the JSON file of tenants, users and
  invoices (`app/data/seed.json` is a sample). Keep the start command, the
  routes, the `X-User-Id` header and the response bodies as they are.
- The PDP address is provided in `CERBOS_GRPC_ADDR` (`host:port`, plaintext
  gRPC). `CERBOS_HTTP_ADDR` (`http://host:port`) is also set if you prefer
  the HTTP API.
- In production the PDP runs with default settings and loads
  `/workspace/policies` from disk. Some environments enable strict
  evaluation, and the service must behave the same either way.
- Production data has many more tenants, users and invoices than the sample,
  so do not rely on particular IDs.
