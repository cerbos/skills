# Hide the document buttons people can't use

Our documents app shows **Edit** and **Delete** on every row to everyone. When
someone clicks a button they aren't allowed to use, the API refuses with a 403,
which is correct but a poor experience. Please change the browser app so each
row only shows the buttons the signed-in user can actually use.

Constraints from the team:

- The decision must be made in the browser, with no request to our API or to a
  PDP for each button. The list can be long and we don't want a round trip per
  row.
- The rules must stay in our Cerbos policies, not get copied into React. We
  already publish them through Cerbos Hub: the `acme-docs-prod` deployment (ID
  `F5D3RW8KJ2HQ`) has an embedded PDP rule named `docs-ui` (rule ID
  `B7XK2M9QPL4R`). The rule has public access and is filtered to the
  `document` resource, so the browser can download its bundle directly.
- The API must stay protected exactly as it is today. Keep `npm run server`,
  `npm run build` and the TypeScript type check working.

## The project

- `/workspace/app` — Vite + React + TypeScript app (`src/`) and the Express
  documents API (`server/index.mjs`, run with `npm run server`, listening on
  `PORT`, default 3001). The API identifies the user from the `X-User-Id`
  header and authorizes every edit and delete with our service PDP through
  `@cerbos/http` at `CERBOS_URL` (default `http://localhost:3592`). The dev
  server proxies `/api` to it.
- `/workspace/cerbos` — the `document` policy (also in our Hub policy store),
  the local PDP config, the production config, and `.env` with the Hub client
  credential our service PDPs use.

Node 22 and the app's dependencies are installed in `/workspace/app/node_modules`.
The Cerbos JavaScript SDK packages (`@cerbos/*`) are pre-installed there and in
the npm cache at the versions we use, but are not yet declared in
`package.json`; install from the cache rather than upgrading them. Cerbos 0.55.0
is installed natively if you want to run the PDP locally
(`cerbos server --config /workspace/cerbos/config.yaml`); Docker is not
available. This sandbox has no access to our Hub account, so the real bundle
won't load here.
