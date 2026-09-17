# Masking sensitive fields

Masks are applied at the PDP before an entry is written to the local buffer, so a masked value is neither stored on disk nor transmitted to Cerbos Hub. Cerbos Hub retains whatever it receives, which makes this the one place data can be kept inside the perimeter.

`mask` is a setting of the `hub` audit backend. The `local`, `file` and `kafka` backends have no equivalent; for those, keep data out at the source with `includeMetadataKeys` / `excludeMetadataKeys` (below) or by not putting it in the request.

## The four sections

```yaml
audit:
  enabled: true
  backend: hub
  hub:
    storagePath: /var/cerbos/audit
    mask:
      metadata:
        - x-api-key
      peer:
        - address
        - forwardedFor
      checkResources:
        - inputs[*].principal.attr.ssn
        - inputs[*].auxData
      planResources:
        - input.principal.attr.ssn
```

| Section | Paths are rooted at | Applies to |
|---|---|---|
| `metadata` | the entry's captured request-metadata map | access **and** decision entries |
| `peer` | the entry's `peer` message | access **and** decision entries |
| `checkResources` | `decisionLogEntry.checkResources` | decision entries from `CheckResources` calls |
| `planResources` | `decisionLogEntry.planResources` | decision entries from `PlanResources` calls |

A section whose only entry is `'*'` is cleared wholesale — `peer: ['*']` removes peer information from every entry.

## Path syntax

A supported subset of JSONPath:

| Form | Example |
|---|---|
| Dot accessor | `input.principal.attr.ssn` |
| Bracket accessor | `['input']['principal']['attr']['ssn']` |
| Mixed | `inputs[*]['principal']['attr']['ssn']` |
| List index | `inputs[0].principal.id` |
| List wildcard | `inputs[*].principal.attr.ssn` |

Nesting continues through maps, so `inputs[*].principal.attr.profile.dateOfBirth` reaches a key inside an attribute that holds an object.

**Segments that name a protobuf field must use the lowerCamelCase JSON name**: `forwardedFor`, `auxData`, `filterDebug`, `requestId`, `checkResources`. Segments that name a *map key* — anything below `metadata`, `principal.attr`, `resource.attr` or `auxData.jwt` — are matched literally, exactly as the key appears in the data.

This matters because **a path that matches nothing is not an error**. It is accepted at startup and quietly masks nothing, so a typo or a snake_case field name looks like a working mask and ships the data anyway. The `peer` example published in the Cerbos Hub documentation uses `forwarded_for`, which matches no field; the working form is `forwardedFor`. Verify every mask against real data before trusting it.

Deletion, not redaction: a masked field is removed from the entry rather than replaced with a placeholder, and removing the last remaining key of a map removes the map.

## Worked examples

| To keep out of the audit trail | Mask |
|---|---|
| `Authorization` header | Nothing to do — never captured. See *Request metadata* below. |
| Another secret-bearing header, e.g. `x-api-key` | `metadata: ['x-api-key']`, or better `excludeMetadataKeys` so it applies to every backend |
| Caller IP addresses | `peer: [address, forwardedFor]` |
| A PII principal attribute | `checkResources: ['inputs[*].principal.attr.ssn']` and `planResources: ['input.principal.attr.ssn']` — both, since the two call kinds are separate sections |
| PII nested inside an attribute | `inputs[*].principal.attr.profile.dateOfBirth` |
| Everything a JWT carried | `checkResources: ['inputs[*].auxData']` |
| One JWT claim | `checkResources: ['inputs[*].auxData.jwt.email']` |
| Resource content — document bodies, amounts | `checkResources: ['inputs[*].resource.attr.body']` |
| Values emitted by policy `output` blocks | `checkResources: ['outputs[*].outputs']` |

`outputs` on its own is the whole `CheckOutput` list: the per-action effects, the effective derived roles and the validation errors as well as the rule outputs. Masking it leaves an entry that no longer records which actions were allowed or denied. Reach one level deeper, as above, when the target is only the values policies emitted.

The same caution applies to `inputs[*].principal.id` and `inputs[*].resource.id`: maskable, but the entry then attributes the decision to nobody, and Hub's principal rankings and filters lose it with it.

## Request metadata

Metadata capture happens before masks run, and it decides what exists to be masked. Both settings are top-level `audit` settings, so they apply to every backend.

| `includeMetadataKeys` | `excludeMetadataKeys` | Captured |
|---|---|---|
| empty | empty | nothing |
| set | empty | only the listed keys |
| empty | set | everything except the listed keys |
| set | set | the include list, minus anything also in the exclude list |

Both are empty by default, so **no request metadata is recorded at all** until you ask for it. `authorization` and `grpc-trace-bin` are excluded unconditionally, whatever the lists say. HTTP headers arrive as gRPC metadata, so header names are the keys here.

Prefer these for dropping a whole header, and keep the `metadata` mask for a Hub-specific extra on top.

## Finding and verifying paths

Find the paths by looking at a real entry. In a development environment, run the PDP with the `local` backend and read one back:

```bash
cerbosctl audit --kind=decision --tail=1 --raw
```

The JSON that comes back is the shape the mask paths address, minus the section prefix that `checkResources` or `planResources` supplies.

Verify the mask by watching what the `hub` backend actually emits. Masks are applied before the secondary output is written, so a pipe to stdout prints exactly the entry Hub will receive:

```yaml
audit:
  enabled: true
  backend: hub
  hub:
    storagePath: /var/cerbos/audit
    mask:
      checkResources:
        - inputs[*].principal.attr.ssn
    pipeOutput:
      enabled: true
      backend: file
  file:
    path: stdout
```

Drive a representative request and read the line. That ordering is also the warning: `pipeOutput` is not a full-fidelity local copy — a SIEM fed from it receives the masked entries too, so anything a downstream system needs must survive the mask. The `hub` backend cannot pipe to itself.

## Size guard

An entry larger than roughly 4 MiB has `principal.attr` and `resource.attr` (plus `output.filterDebug` for plans) stripped automatically and is flagged `oversized` on the record. It is a transport guard, not a privacy control — mask deliberately rather than relying on it.

## What has no mask

There is no mask section for `callId`, `timestamp`, `method`, `statusCode`, `policySource`, the `auditTrail` of effective policies, or `requestContext.annotations`. Annotations in particular are recorded exactly as the caller sent them, so treat that field as public within the workspace.

## What Synapse adds

Synapse enriches a request before the PDP evaluates it, so the decision entry records what was actually evaluated rather than what the client sent. An attribute a proxy extension fetched from an internal directory appears in the entry's inputs alongside the client's own.

Synapse also annotates each request's `requestContext`, and those annotations ride through to every entry Hub ingests:

| Annotation | Value |
|---|---|
| `cerbos.dev/synapse/version` | The running Synapse version. Always added. |
| `cerbos.dev/synapse/extensions` | The proxy extensions that processed the request, in the order they ran. Added when any are configured. |
| your own keys | String, number or boolean values from the top-level `audit.instanceAnnotations` block — environment, region, cluster. |

With the embedded PDP, the audit block nests under `pdp.inProcess`:

```yaml
pdp:
  inProcess:
    audit:
      enabled: true
      backend: hub
      hub:
        storagePath: /var/lib/synapse/audit
```

Fronting an existing PDP fleet instead (`pdp.external`), Hub credentials and the audit block live on the upstream PDP; the top-level `audit.instanceAnnotations` still applies, because Synapse adds them before forwarding.

Canonical reference: [Cerbos Hub audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-audit-insights) and the [audit configuration block](https://docs.cerbos.dev/cerbos/latest/configuration/audit.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-audit-insights).
