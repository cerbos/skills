# TypeScript / Node.js integration recipe

**SDK packages**: [@cerbos/grpc](https://www.npmjs.com/package/@cerbos/grpc) (server-side Node, default), [@cerbos/http](https://www.npmjs.com/package/@cerbos/http) (edge/serverless/browser), [@cerbos/core](https://www.npmjs.com/package/@cerbos/core) (shared types — installed transitively), [@cerbos/react](https://www.npmjs.com/package/@cerbos/react) + [@cerbos/embedded](https://www.npmjs.com/package/@cerbos/embedded) (UI-state hooks only)
**Live sources — fetch these before writing any integration code:**
- SDK repo README: https://raw.githubusercontent.com/cerbos/cerbos-sdk-javascript/main/README.md
- SDK API docs: https://cerbos.github.io/cerbos-sdk-javascript/
- Query-plan adapters: https://github.com/cerbos/query-plan-adapters (packages `@cerbos/orm-prisma`, `@cerbos/orm-drizzle`, `@cerbos/orm-mongoose` — read each package README)
- Docs index: https://docs.cerbos.dev/llms.txt

Notes that apply everywhere below: the SDK packages are ESM-only (but `require`-able from CommonJS on Node 20.19.5+/22.15+/24+); principal/resource attributes use the `attr` key (`attributes` is deprecated); and `result.isAllowed(action)` returns `boolean | undefined`, so always compare `=== true` — unknown must never become allow.

## 1. Client setup

Server-side Node talks gRPC to the PDP (port 3593). Use `@cerbos/http` (port 3592) only where gRPC is unavailable: edge runtimes (Cloudflare Workers, Vercel Edge), browsers, or serverless platforms without native gRPC support. Both extend the same `Client` base from `@cerbos/core`, so all snippets below work with either.

```console
npm install @cerbos/grpc
```

One client per process, created at module scope — never per request. gRPC multiplexes over a single channel; per-request construction leaks connections.

```typescript
// src/lib/cerbos.ts
import { GRPC } from "@cerbos/grpc";

export const cerbos = new GRPC(process.env.CERBOS_ADDRESS ?? "localhost:3593", {
  tls: process.env.CERBOS_TLS === "true",
});
```

`tls` accepts `boolean` or a Node `tls.SecureContext` (from `tls.createSecureContext(...)`) for custom CAs or mutual TLS. Call `cerbos.close()` on graceful shutdown (safe to call more than once). The HTTP client is `new HTTP(process.env.CERBOS_URL ?? "http://localhost:3592")` — same methods, `fetch`-based. `@cerbos/react` + an Embedded PDP client is a convenience for hiding/disabling UI elements only; it is never the enforcement point — the server-side check is.

## 2. Principal construction

One canonical helper maps the app's existing auth context (JWT claims, session object, auth middleware output) to a Cerbos `Principal`. Every check and every plan call goes through it, so principal drift between endpoints is impossible.

```typescript
// src/lib/principal.ts
import type { Principal } from "@cerbos/core";

// Adapt AuthUser to whatever your auth middleware attaches (JWT payload, session user, ...).
export interface AuthUser {
  id: string;
  roles: string[];
  department?: string;
  tenantId?: string;
}

export function toPrincipal(user: AuthUser): Principal {
  return {
    id: user.id,
    roles: user.roles, // must be non-empty; map your app's role model here
    attr: {
      // Only attributes referenced by policy conditions — not the whole user object.
      department: user.department ?? "",
      tenantId: user.tenantId ?? "",
    },
  };
}
```

Optionally bind it once per request with `cerbos.withPrincipal(toPrincipal(user))`, which returns a client whose `isAllowed`/`checkResource(s)`/`planResources` omit the principal argument.

## 3. Framework integration points

Placement follows [ARCHITECTURE.md](../ARCHITECTURE.md): coarse route-level gates may live in middleware/guards, but any decision that depends on resource attributes belongs in the service layer, after the resource is loaded — never a fetch-then-filter in middleware.

### Express

Middleware handles authentication and principal construction; the route/service does the resource-aware check.

```typescript
// Auth middleware attaches req.user (your existing auth). Then:
import { cerbos } from "./lib/cerbos";
import { toPrincipal } from "./lib/principal";

app.get("/documents/:id", async (req, res) => {
  const document = await documentService.findById(req.params.id);
  if (!document) return res.status(404).json({ error: "not found" });

  const allowed = await cerbos.isAllowed({
    principal: toPrincipal(req.user),
    resource: {
      kind: "document",
      id: document.id,
      attr: { ownerId: document.ownerId, status: document.status },
    },
    action: "view",
  });
  if (allowed !== true) return res.status(403).json({ error: "forbidden" });

  res.json(document);
});
```

A coarse gate on a whole router may call `isAllowed` from a middleware factory with a kind-only resource (`{ kind, id: "new" }`); keep attribute-dependent checks in handlers/services.

### NestJS

A guard covers coarse, pre-load checks; an injectable service wraps the client for resource-aware checks inside providers. Register the client once via a provider so it is a process singleton.

```typescript
// cerbos.module.ts
import { Global, Module } from "@nestjs/common";
import { GRPC } from "@cerbos/grpc";

export const CERBOS = Symbol("CERBOS");

@Global()
@Module({
  providers: [
    {
      provide: CERBOS,
      useFactory: () =>
        new GRPC(process.env.CERBOS_ADDRESS ?? "localhost:3593", {
          tls: process.env.CERBOS_TLS === "true",
        }),
    },
  ],
  exports: [CERBOS],
})
export class CerbosModule {}
```

```typescript
// document.service.ts
import { ForbiddenException, Inject, Injectable } from "@nestjs/common";
import type { GRPC } from "@cerbos/grpc";
import { CERBOS } from "./cerbos.module";
import { toPrincipal, type AuthUser } from "./principal";

@Injectable()
export class DocumentService {
  constructor(@Inject(CERBOS) private readonly cerbos: GRPC) {}

  async view(user: AuthUser, id: string): Promise<Document> {
    const document = await this.repo.findById(id);

    const allowed = await this.cerbos.isAllowed({
      principal: toPrincipal(user),
      resource: { kind: "document", id: document.id, attr: { ownerId: document.ownerId } },
      action: "view",
    });
    if (allowed !== true) throw new ForbiddenException();
    return document;
  }
}
```

A `CanActivate` guard (or interceptor) calling the same client is appropriate only when the decision needs nothing from the database — e.g. gating `POST /documents` on the principal alone.

### Next.js (App Router)

Checks live in route handlers and server actions — server-side only. Keep the client in a module (`src/lib/cerbos.ts` as above); in dev, guard against hot-reload re-instantiation the same way you do for Prisma (stash on `globalThis`). On Edge runtime, swap `GRPC` for `HTTP` — same call sites.

```typescript
// app/documents/[id]/route.ts
import { NextResponse } from "next/server";
import { cerbos } from "@/lib/cerbos";
import { toPrincipal } from "@/lib/principal";
import { getSessionUser } from "@/lib/auth";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const user = await getSessionUser();
  if (!user) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const document = await db.document.findUnique({ where: { id } });
  if (!document) return NextResponse.json({ error: "not found" }, { status: 404 });

  const allowed = await cerbos.isAllowed({
    principal: toPrincipal(user),
    resource: { kind: "document", id: document.id, attr: { ownerId: document.ownerId } },
    action: "view",
  });
  if (allowed !== true) return NextResponse.json({ error: "forbidden" }, { status: 403 });

  return NextResponse.json(document);
}
```

Server actions follow the same shape: check at the top of the action, throw/return an error on deny. Client components may use `@cerbos/react` hooks to hide buttons, but the action/route handler always re-checks.

## 4. Single-resource checks

`isAllowed` for one action; `checkResource` when you need several actions in one round trip (e.g. returning UI permissions alongside the resource); `checkResources` for several resources at once.

```typescript
const decision = await cerbos.checkResource({
  principal: toPrincipal(user),
  resource: {
    kind: "document",
    id: document.id,
    attr: { ownerId: document.ownerId, status: document.status },
  },
  actions: ["view", "edit", "delete"],
});

if (decision.isAllowed("view") !== true) throw new ForbiddenError();

return {
  ...document,
  permissions: {
    canEdit: decision.isAllowed("edit") === true,
    canDelete: decision.isAllowed("delete") === true,
  },
};
```

`decision.allowedActions()` returns the allowed subset directly. For heterogeneous batches, `checkResources({ principal, resources: [{ resource, actions }, ...] })` returns a response with `isAllowed({ resource: { kind, id }, action })`. Client errors (PDP unreachable, validation failure) throw — let them propagate to a 5xx or catch-and-deny; never catch-and-allow.

## 5. List filtering

Never fetch-then-filter. For list/search endpoints, ask Cerbos for a query plan and compile it into the ORM's native filter with the adapter for your ORM (all from https://github.com/cerbos/query-plan-adapters). Every adapter returns the same three-way outcome, which must be handled explicitly:

- `PlanKind.ALWAYS_ALLOWED` — run the query with no extra filter.
- `PlanKind.ALWAYS_DENIED` — return an empty result without touching the database.
- `PlanKind.CONDITIONAL` — apply the produced filter, AND-ed with existing app filters.

The `mapper` translates policy attribute references (`request.resource.attr.*`, and `request.principal.attr.*` where policies compare principals) to model fields. Keep it next to the resource kind's repository so policy and mapper evolve together.

### Prisma — `@cerbos/orm-prisma`

```typescript
import { queryPlanToPrisma, PlanKind } from "@cerbos/orm-prisma";

const plan = await cerbos.planResources({
  principal: toPrincipal(user),
  resource: { kind: "document" },
  action: "view",
});

const result = queryPlanToPrisma({
  queryPlan: plan,
  mapper: {
    "request.resource.attr.ownerId": { field: "ownerId" },
    "request.resource.attr.status": { field: "status" },
    "request.resource.attr.department": { field: "department" },
  },
});

if (result.kind === PlanKind.ALWAYS_DENIED) return [];

return prisma.document.findMany({
  where:
    result.kind === PlanKind.CONDITIONAL
      ? { AND: [result.filters, { deletedAt: null }] }
      : { deletedAt: null },
});
```

### Drizzle — `@cerbos/orm-drizzle`

The mapper values are Drizzle columns (or SQL fragments); the result's `filter` is a SQL expression composable with `and(...)`.

```typescript
import { queryPlanToDrizzle, PlanKind } from "@cerbos/orm-drizzle";
import { and, eq } from "drizzle-orm";
import { documents } from "./schema";

const result = queryPlanToDrizzle({
  queryPlan: plan,
  mapper: {
    "request.resource.attr.ownerId": documents.ownerId,
    "request.resource.attr.status": documents.status,
  },
});

if (result.kind === PlanKind.ALWAYS_DENIED) return [];
return db
  .select()
  .from(documents)
  .where(
    result.kind === PlanKind.CONDITIONAL
      ? and(eq(documents.deleted, false), result.filter)
      : eq(documents.deleted, false),
  );
```

### Mongoose — `@cerbos/orm-mongoose`

```typescript
import { queryPlanToMongoose, PlanKind } from "@cerbos/orm-mongoose";

const result = queryPlanToMongoose({
  queryPlan: plan,
  mapper: { "request.resource.attr.ownerId": { field: "ownerId" } },
});

if (result.kind === PlanKind.ALWAYS_DENIED) return [];
return DocumentModel.find(
  result.kind === PlanKind.CONDITIONAL ? { $and: [result.filters, { deleted: false }] } : { deleted: false },
);
```

Adapters throw on operators they cannot translate — treat that as deny (empty list) plus an error log, not as "no filter".

## 6. Shadow-mode wrapper

The ecosystem implementation of the shadow-check pattern in [ARCHITECTURE.md](../ARCHITECTURE.md). Contract: in `shadow` mode the legacy boolean stays authoritative and Cerbos runs in parallel without ever blocking or failing the response; mismatches emit exactly one structured JSON log line; in `enforce` mode the Cerbos decision is returned and errors deny (fail closed). Mode is chosen per callsite so endpoints cut over one at a time.

```typescript
// src/lib/shadow-check.ts
import type { CheckResourceRequest } from "@cerbos/core";
import { cerbos } from "./cerbos";

export type AuthzMode = "shadow" | "enforce";

// Per-callsite cutover: AUTHZ_MODE_DOCUMENT_VIEW=enforce overrides AUTHZ_MODE, default shadow.
export function authzMode(callsite: string): AuthzMode {
  const key = `AUTHZ_MODE_${callsite.toUpperCase().replace(/[^A-Z0-9]+/g, "_")}`;
  const value = process.env[key] ?? process.env.AUTHZ_MODE;
  return value === "enforce" ? "enforce" : "shadow";
}

export interface ShadowCheckInput {
  endpoint: string; // callsite name, e.g. "document.view"
  requestId: string;
  request: CheckResourceRequest & { actions: [string, ...string[]] };
  legacyDecision: () => boolean | Promise<boolean>; // existing authorization logic
  mode?: AuthzMode; // defaults to authzMode(endpoint)
}

export async function shadowCheck(input: ShadowCheckInput): Promise<boolean> {
  const { endpoint, requestId, request, legacyDecision } = input;
  const mode = input.mode ?? authzMode(endpoint);
  const action = request.actions[0];

  if (mode === "enforce") {
    // Cerbos is authoritative. Errors and undefined results deny.
    try {
      const decision = await cerbos.checkResource(request);
      return decision.isAllowed(action) === true;
    } catch {
      return false; // fail closed
    }
  }

  // Shadow mode: legacy is authoritative; Cerbos runs in parallel and must never
  // block or fail the response.
  const [legacy, cerbosOutcome] = await Promise.all([
    Promise.resolve(legacyDecision()),
    cerbos
      .checkResource(request)
      .then((decision) => ({ ok: true as const, allowed: decision.isAllowed(action) === true }))
      .catch((error: unknown) => ({ ok: false as const, error })),
  ]);

  if (cerbosOutcome.ok && cerbosOutcome.allowed !== legacy) {
    console.log(
      JSON.stringify({
        event: "cerbos_shadow_mismatch",
        endpoint,
        principalId: request.principal.id,
        resourceKind: request.resource.kind,
        resourceId: request.resource.id,
        action,
        legacy,
        cerbos: cerbosOutcome.allowed,
        requestId,
      }),
    );
  }

  return legacy;
}
```

Callsite usage — the only change to existing code is wrapping the legacy check:

```typescript
const allowed = await shadowCheck({
  endpoint: "document.view",
  requestId: req.id,
  request: {
    principal: toPrincipal(req.user),
    resource: { kind: "document", id: document.id, attr: { ownerId: document.ownerId } },
    actions: ["view"],
  },
  legacyDecision: () => legacyCanViewDocument(req.user, document),
});
if (!allowed) return res.status(403).json({ error: "forbidden" });
```

Cutover per endpoint: watch `cerbos_shadow_mismatch` for `document.view` reach zero over a representative window, set `AUTHZ_MODE_DOCUMENT_VIEW=enforce`, then delete `legacyCanViewDocument` once every callsite is enforced. Route the log line through your structured logger if `console.log` is not your sink, keeping the field names exactly as above.

## 7. Testing

Integration-test decisions against a real PDP loaded with the real policies — not mocks. With [testcontainers](https://www.npmjs.com/package/testcontainers):

```typescript
// test/cerbos.setup.ts
import { GenericContainer, Wait, type StartedTestContainer } from "testcontainers";
import { GRPC } from "@cerbos/grpc";

export async function startCerbos(policiesDir: string): Promise<{
  container: StartedTestContainer;
  client: GRPC;
}> {
  const container = await new GenericContainer("ghcr.io/cerbos/cerbos:latest")
    .withCommand(["server"])
    .withExposedPorts(3592, 3593)
    .withBindMounts([{ source: policiesDir, target: "/policies", mode: "ro" }])
    .withWaitStrategy(Wait.forLogMessage("Starting gRPC server"))
    .start();

  const client = new GRPC(`localhost:${container.getMappedPort(3593)}`, { tls: false });
  return { container, client };
}
```

```typescript
// test/document.authz.test.ts (vitest/jest shape)
let cerbos: GRPC;
let container: StartedTestContainer;

beforeAll(async () => {
  ({ client: cerbos, container } = await startCerbos(path.resolve(__dirname, "../policies")));
});

afterAll(async () => {
  cerbos.close();
  await container.stop();
});

test("owner can edit own document", async () => {
  const allowed = await cerbos.isAllowed({
    principal: { id: "alice", roles: ["USER"] },
    resource: { kind: "document", id: "doc1", attr: { ownerId: "alice" } },
    action: "edit",
  });
  expect(allowed).toBe(true);
});
```

Inject the test client into the app under test through whatever seam holds the singleton (DI provider in NestJS, module mock, or a `CERBOS_ADDRESS` env pointing at the mapped port). For pure policy-logic tests, prefer Cerbos's own YAML test suites (`cerbos compile --tests`) and keep app-level tests focused on wiring: principal construction, mapper correctness, deny paths returning 403/empty lists.

## 8. Local dev PDP

```yaml
# docker-compose.yml
services:
  cerbos:
    image: ghcr.io/cerbos/cerbos:latest
    command: ["server"]
    ports:
      - "3592:3592" # HTTP
      - "3593:3593" # gRPC
    volumes:
      - ./policies:/policies:ro
```

The default disk storage driver watches `/policies` for changes, so policy edits apply without restarting the container. Point the app at it with `CERBOS_ADDRESS=localhost:3593` (gRPC) or `CERBOS_URL=http://localhost:3592` (HTTP).
