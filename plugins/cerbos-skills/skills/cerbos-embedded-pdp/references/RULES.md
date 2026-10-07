# ePDP rules

The Hub-side half of an embedded PDP. A rule decides which policies go into a bundle, who may download it, and from where. Full reference: [ePDP rules](https://docs.cerbos.dev/cerbos-hub/deployments-epdp-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_hub-deployments-epdp-rules).

A deployment can carry several rules, so shape one per client rather than one per deployment:

- a minimal bundle for browser clients, holding only the policies behind the UI
- a full bundle for edge workers that enforce
- one rule with dynamic scopes serving every tenant in a multi-tenant application

## Lifecycle

Create: deployment → **Embedded PDP rules** → **Create rule** → name → configure → **Save rule**. The card then shows the 12-character rule ID, with **Copy** beside it.

Each card also carries **Edit**, **Duplicate** (the way to derive a variant of a working rule) and **Delete**, plus an enable/disable toggle. A disabled rule serves nothing: clients asking for its bundle get an error, which makes the toggle the lever for revoking access during an incident, or for staging a rule before clients exist. Re-enabling restores service without changing the rule ID.

## Filtering the bundle

Filters are applied when the bundle is requested and leave the source policies untouched, so filtering is a per-rule decision, not a policy change.

Two reasons to filter, and the second is the one that gets skipped:

- **Size.** A browser checking three resource kinds does not need the other fifty.
- **Disclosure.** A bundle served to an end-user browser is readable by that user. Filtering keeps server-side authorization logic out of it.

| Setting | Effect |
|---|---|
| **Resources and actions** | Per-entry: resources only (all actions on those kinds), actions only (that action across all kinds), or both (the intersection). Across entries the bundle is the **union** — a rule with entries `document:{view,edit}` and `folder:{view}` includes rules matching either. |
| **Roles** | `Specific` keeps only rules referencing the named roles. An editor-and-viewer UI need not ship the `admin` rules. |
| **Versions** | `Specific` keeps only the named [policy versions](https://docs.cerbos.dev/cerbos/latest/policies/resource_policies?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_pdp-policies-resource-policies), which is how a legacy client stays on `v1` while the current one gets `v2`. |
| **Scopes** | `All`, `Specific`, or `Require specific scope at fetch time`. See below. |

Leaving a filter empty or set to `All` includes everything of that kind.

### Scopes

[Scoped policies](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_pdp-policies-scoped-policies) carry multi-tenancy and hierarchical overrides, and a scope request always pulls its ancestors: asking for `acme.eu.prod` returns policies for `acme.eu.prod`, `acme.eu`, `acme`, and the root scope, so inherited rules stay evaluable.

**Specific** (static) pins the scopes in the rule definition. Reach for it when the set is small, known ahead of time, stable, and the same for every client on the rule.

**Require specific scope at fetch time** (dynamic) makes the client name its scopes on each download, and the bundle is filtered to them. This is the answer for one-scope-per-tenant: one rule serves thousands of tenants instead of thousands of rules.

```typescript
const cerbos = new Embedded({
  policies: {
    ruleId: "<RULE_ID>",
    scopes: [currentTenant.scopeId],
  },
  wasm,
});
```

Two constraints worth knowing before designing around dynamic scopes:

- A rule that also has scope patterns configured **rejects** requests for scopes outside them. The patterns are the allowlist.
- A single request carries at most 128 scopes, each non-empty and distinct.

Scopes are fixed for the life of a client, so switching tenant means constructing a new `Embedded` client.

## Who may download

Start from what a leaked bundle would reveal: the resource kinds and actions that exist, the conditions under which access is granted, the roles and what each grants, and which principal and resource attributes steer decisions. For a documented API with plain RBAC that may be public knowledge already; for proprietary rules it is a map of the system. The [threat model section](https://docs.cerbos.dev/cerbos-hub/deployments-epdp-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_hub-deployments-epdp-rules#_threat_model) frames the call.

### Authentication

`Public access` serves the bundle to anyone holding the rule ID. `Client credential` requires a client ID and secret, issued from the deployment's **Client credentials** tab — the same credentials service PDPs use.

Client credentials belong only where the user cannot read them, which rules them out of browser JavaScript. Three ways to authenticate a browser, in the order they usually fit:

| Pattern | How it works |
|---|---|
| Backend-for-frontend | The server downloads the bundle with its credentials and serves the bytes to the browser, which never sees them. Pass the downloaded bundle to the client as `policies` (see [CLIENT.md](CLIENT.md)). |
| Server-side rendering | The server evaluates with a service PDP and sends results down. No bundle reaches the browser at all. |
| Public bundle | When the logic is not sensitive, leave authentication off and serve browsers directly. |

Node servers, edge workers with secret storage, and other server-side runtimes hold credentials safely — in environment variables or a secrets manager.

### IP allowlist

CIDR ranges, IPv4 and IPv6, checked on the **download request** and independent of authentication. `203.0.113.42/32` pins a single address; `0.0.0.0/0` admits every IPv4 address and so turns the allowlist off.

The allowlist governs the download only. A client that has the bundle evaluates it from anywhere, which makes this defence-in-depth around distribution — a corporate range, a CDN provider's ranges — rather than a control on evaluation.
