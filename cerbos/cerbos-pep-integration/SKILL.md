---
name: cerbos-pep-integration
description: Integrate an application with a Cerbos PDP — the policy enforcement point. Covers SDK choice for JavaScript, Go, Python, Java, .NET, Rust, PHP and Ruby; building the principal, resource, actions and JWT auxiliary data; choosing between `isAllowed`, `checkResource` and `checkResources`; and filtering queries by permission with `planResources` and its ORM adapters. Use when calling Cerbos from application code, enforcing a permission check in a request handler, filtering a query or list by permission, passing JWT claims to the PDP, or choosing a Cerbos SDK package.
license: Apache-2.0
metadata:
  author: cerbos
  version: "1.0"
---

# Cerbos PEP Integration

A **PEP** — policy enforcement point — is the code in your application that calls a PDP and acts on the answer. Policies decide nothing until a PEP asks.

## The PDP is stateless

This is the fact that shapes every integration, and the one most often missed. The PDP holds policies and nothing else: no users, no roles, no rows, no session. It never fetches anything. Every check carries all of its own context, and the PEP supplies it — the principal's id and roles, the resource's kind, id and attributes, and the actions.

A condition over `R.attr.owner` in a request that carried no `owner` attribute evaluates to a denial, not an error. A missing attribute is indistinguishable from a legitimate "no".

Two consequences:

- **Load the resource before you check it.** You cannot authorize a document you have not read. The exception is a list, where the query plan inverts the order.
- **Mapping your user store onto the principal is the PEP's job.** Keep it in one function per service so a new attribute reaches every check at once.

## Decide

### 1. Where does the check run?

| Context | Use |
|---|---|
| **Server-side enforcement** — API handlers, server actions, background jobs, gateways | A service PDP over gRPC or HTTP. This is the gate; it is the only place a decision binds. |
| **Browser UI** — show, hide, enable, disable | An embedded PDP evaluating a Hub-built policy bundle in-process, with no network hop → **`cerbos-embedded-pdp`** skill. |

A browser application usually needs both, and they are not alternatives. The ePDP decides what to render; the server-side check decides what actually happens. A UI-only check is a suggestion, because the request can be replayed by hand.

Calling a service PDP straight from the browser with `@cerbos/http` works and is occasionally right — development, or a shared PDP behind an authenticating proxy — but it exposes the API to policy probing and brings CORS with it. For production browsers, prefer the ePDP, or return a `permissions` map alongside each object in your existing API response.

### 2. What shape is the answer?

| The question | Call |
|---|---|
| May this user do X to this thing? | `isAllowed` — a boolean |
| What may this user do to this thing? | `checkResource` — several actions, one round trip; the way to build a `permissions` map |
| Of these things I already hold, which may they act on? | `checkResources` — a batch, 50 resources × 50 actions per request by default |
| Which things may they see? — a list, a page, a count, an export | `planResources` → **[references/query-plan.md](references/query-plan.md)** |

In most SDKs the first two are implemented on top of `checkResources`, so they cost the same round trip. Choose by intent. Names vary by language, and two SDKs have no `isAllowed` at all — the per-language reference has the exact spelling.

### 3. Pick the language

| Language | Reference | Package |
|---|---|---|
| JavaScript / TypeScript | [references/javascript.md](references/javascript.md) | `@cerbos/grpc`, `@cerbos/http` |
| Go | [references/go.md](references/go.md) | `github.com/cerbos/cerbos-sdk-go` |
| Python | [references/python.md](references/python.md) | `cerbos` (PyPI) |
| Java | [references/java.md](references/java.md) | `dev.cerbos:cerbos-sdk-java` |
| .NET | [references/dotnet.md](references/dotnet.md) | `Cerbos.Sdk` (NuGet) |
| Rust | [references/rust.md](references/rust.md) | `cerbos` (crates.io) |
| PHP / Laravel | [references/php.md](references/php.md) | `cerbos/cerbos-sdk-php`, `cerbos/cerbos-sdk-laravel` |
| Ruby | [references/ruby.md](references/ruby.md) | `cerbos` (gem) |

No SDK for your language: the API is plain gRPC and REST with an OpenAPI document the PDP serves itself. Generate a client — [references/api-shapes.md](references/api-shapes.md).

## Filtering a list

Fetching a page and running `checkResources` over it is the most common wrong turn in a Cerbos integration. It breaks pagination (the database picked the page before authorization ran), makes counts and aggregates impossible, hits the 50-resource ceiling, and pays to read rows nobody may see.

`planResources` inverts it: one call returns the *condition* a resource must satisfy, and an adapter turns that condition into a `WHERE` clause. The database filters, paginates and counts, and the cost stops growing with the size of the list.

Verified adapters: `@cerbos/orm-prisma`, `@cerbos/orm-drizzle`, `@cerbos/orm-mongoose`, `@cerbos/orm-convex`, `@cerbos/langchain-chromadb` (all TypeScript) and `cerbos-sqlalchemy` (Python). Everything else walks the AST, which is a small job. → [references/query-plan.md](references/query-plan.md)

## Where the PEP sits in a request

1. **Authenticate** — establish who the caller is. Cerbos does not do this.
2. **Load** the resource, or for a list skip to the query plan.
3. **Check** — one call, at the boundary of the operation.
4. **Act**, or return 403.

Put the check in the layer that owns the operation — the handler, the service method, the resolver — so one operation has one check in one readable place.

Deny on error. A PDP that is unreachable or past its deadline is an outage; let it surface as a 5xx. Falling through to "allowed" turns an outage into an authorization bypass.

## JWT auxiliary data

Send the raw token as `auxData` and the PDP decodes its claims to `request.auxData.jwt.<claim>`, so policies read them without the PEP unpacking claims into `principal.attr` by hand. The PDP verifies the signature and the `exp`/`nbf` claims against keysets configured in its own `auxData.jwt.keySets` block.

Treat that verification as a tamper check on the hop, not as authentication — Cerbos documents it that way deliberately. Verify the token at your gateway or in the application first. And a raw token puts every claim within the PDP's reach: when a policy needs two claims out of forty, mapping those two into `principal.attr` yourself is the smaller surface.

Single and named-token forms, keyset rules, and the claim paths: [references/api-shapes.md](references/api-shapes.md).

## Connecting to a PDP

The PEP code does not change with where the PDP gets its policies. Disk, a git repository, or a Cerbos Hub bundle — same endpoint, same SDK, same request, same response. Policy distribution is an operational choice, not an integration one.

What it does change is what you operate. Past a single instance on one machine, the recommended production shape is a **Hub-connected PDP**: Hub compiles and tests policies once per change, signs a bundle, pushes it to every connected PDP within seconds, and reports which bundle each one is running. → **`cerbos-hub-setup`** skill.

A local PDP over a policy directory is enough to develop against:

```bash
docker run --rm -p 3592:3592 -p 3593:3593 \
  -v "$(pwd)/policies:/policies" \
  ghcr.io/cerbos/cerbos:latest server
```

- Ports: **3593 gRPC**, **3592 HTTP**. Prefer gRPC from a server; several SDKs offer nothing else.
- Enable TLS whenever the hop leaves the machine. The PDP trusts everything the PEP sends, so the link has to be tamper-proof. Most SDKs default to TLS and want an explicit opt-out for local plaintext; the Ruby and JavaScript gRPC clients make you state it either way, and the Python client and the Laravel package default to *no* TLS — check the language reference before shipping.
- Build the client once per process and share it. It holds a channel or a connection pool.
- [Deployment model](https://docs.cerbos.dev/cerbos/latest/deployment/index) — service, sidecar or DaemonSet — changes latency and blast radius, not your code. A [sidecar](https://docs.cerbos.dev/cerbos/latest/deployment/k8s-sidecar) reached over a Unix domain socket is the lowest-latency option, and most SDKs accept a `unix:` target directly.

## Common mistakes

| Mistake | Instead |
|---|---|
| Checking a fetched list with `checkResources` | `planResources` plus an adapter, so the database filters |
| Handling only `CONDITIONAL` in a query plan | Branch on all three kinds; `ALWAYS_ALLOWED` mishandled blinds admins, `ALWAYS_DENIED` mishandled leaks the table |
| A denial you cannot explain | Set `includeMeta`, then read `matchedPolicy` and `effectiveDerivedRoles`; a missing attribute denies silently |
| Empty `principal.roles` for anonymous users | Send an explicit role such as `anonymous`; at least one role is required |
| Treating a transport error as a decision | Let it propagate and return a 5xx |
| Enforcing in the UI | Enforce on the server; use the ePDP for what to render |
| A new client per request | One client per process |
| Trusting a JWT because the PDP verified it | Verify at the gateway or in the app; the PDP check guards the hop |
| Discarding `cerbosCallId` | Log it next to your request ID — it is the link to the PDP's audit entry |

## References

| Reference | When |
|---|---|
| [references/api-shapes.md](references/api-shapes.md) | The wire request and response, required fields, batch limits, the condition AST, `auxData`, curl and grpcurl. Ground truth when an SDK's naming is ambiguous. |
| [references/query-plan.md](references/query-plan.md) | Filtering any list or query. Adapters, mappers, operator coverage per store, and how to write your own. |
| `references/<language>.md` | Install, connect, the four calls, and the query-plan adapter for one language. See the table above. |

Writing or changing the policies themselves is the **`cerbos-policy`** skill. Getting them to a PDP is **`cerbos-hub-setup`**. Browser-side evaluation is **`cerbos-embedded-pdp`**.
