---
name: cerbos-audit-insights
description: Cerbos audit logs and Cerbos Hub Insights. Use when enabling audit or decision logging, getting a PDP or Synapse instance to emit decisions at all, debugging an application that allows or denies the wrong thing, masking PII, tokens or headers before entries leave the network, or answering a compliance audit-trail question (SOC 2, ISO 27001, HIPAA, PCI DSS, GDPR). Not for why a policy evaluates the way it does at authoring time, which is `cerbos-policy`.
license: Apache-2.0
metadata:
  author: cerbos
  version: "1.0"
---

# Cerbos Audit and Insights

A Cerbos PDP records every API call it serves and every decision it makes. Where those records go, and what you can ask of them afterwards, is the choice this skill covers.

| Backend | Records land | Queried with | Across a fleet |
|---|---|---|---|
| `local` | Embedded key-value store on the PDP | Admin API, `cerbosctl audit`, `cerbosctl decisions` | One PDP at a time |
| `file` | Newline-delimited JSON, a file or stdout/stderr | Whatever agent collects the file | Only what you build |
| `kafka` | A Kafka topic (JSON or protobuf) | Your consumers | Only what you build |
| `hub` | Local buffer on the PDP, streamed to Cerbos Hub | Hub console — audit log search, Insights, exports | Yes |

Aggregation across instances, fleet-wide search and the Insights dashboards are **Cerbos Hub** capabilities. A standalone PDP writes a complete audit trail through the other three backends; what it has no answer for is collecting and querying that trail across every instance. Full backend reference: [audit configuration](https://docs.cerbos.dev/cerbos/latest/configuration/audit?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_pdp-configuration-audit).

## Enabling collection

Three things: a credential, the backend, and somewhere to buffer.

**1. Credential.** In the Hub console, open the deployment's **Client credentials** tab and generate a **Read & write** credential. The secret is shown once. Audit upload writes, so a read-only credential cannot ship logs, and a policy store credential is a different credential entirely. One read & write deployment credential covers both bundle download and audit upload.

**2. Configuration.**

```yaml
hub:
  credentials:
    clientID: "..."
    clientSecret: "..."
    pdpID: "orders-pdp-01"   # optional; names this instance in Hub. Random if omitted.
audit:
  enabled: true
  backend: hub
  hub:
    storagePath: /var/cerbos/audit
```

The credentials also read from `CERBOS_HUB_CLIENT_ID`, `CERBOS_HUB_CLIENT_SECRET` and `CERBOS_HUB_PDP_ID`.

`audit.enabled: true` turns on both kinds of entry: `accessLogsEnabled` and `decisionLogsEnabled` both default to **true**. The generated configuration reference prints `false` beside them, which is an illustrative value rather than the default.

Policies do not have to come from Hub for this to work. The `hub` audit backend needs only `hub.credentials`, so a PDP serving policies from disk, git, a database or blob storage can still ship its audit trail — and each entry records which source the policies came from.

**3. `storagePath` is a buffer, not a disposable cache.** Entries are written there first and removed once Hub has acknowledged them, so a network interruption or a PDP crash costs nothing: the backlog goes up on the next start. Under an orchestrator, attach a persistent volume at that path. Buffered records are kept for `retentionPeriod`, 168h by default.

**4. Verify.** Drive a `CheckResources` call, then open the workspace's **Audit logs** → **Decision logs**. Batches flush on an interval, so give it a moment. If nothing arrives, walk this list:

- `audit.enabled` is `true` and `audit.backend` is `hub`
- `audit.hub.storagePath` is set and writable, and the volume has space — a full volume stops new entries being buffered
- the credential is **Read & write**, not read-only
- the PDP appears under the deployment's **Decision points** tab, so it is reaching Hub at all
- the volume is persistent — a PDP that crashes between syncs loses whatever an `emptyDir` was holding

More causes: [troubleshooting](https://docs.cerbos.dev/cerbos-hub/troubleshooting?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-troubleshooting).

## What a request records

Two entries per API call, sharing one call ID:

| Entry | Holds |
|---|---|
| **Access** | Call ID, timestamp, peer (address, forwarded-for, user agent, auth info), captured request metadata, gRPC method, status code, policy source |
| **Decision** | Call ID, timestamp, peer, metadata, policy source, and either the `CheckResources` inputs and outputs or the `PlanResources` input and output — principal and resource attributes, actions, per-action effects, effective derived roles, rule outputs, and the audit trail of policies that were effective |

Invalid and unauthenticated requests produce an access entry and no decision entry, which is how misconfigured clients and unauthorized attempts show up.

Every Cerbos API response carries a `cerbosCallId`. Log it from the calling application and an application-side incident joins straight onto the Cerbos record.

Callers can attach `requestContext.annotations` to a request — arbitrary key-value pairs, recorded on both entries. Useful for tenant, environment or trace identifiers; keep secrets out, because there is no mask for them.

## Choosing which decisions are logged

`decisionLogFilters` drops entries at the PDP, before any backend sees them. All default off.

| Setting | Drops |
|---|---|
| `checkResources.ignoreAllowAll` | Any `CheckResources` decision entry containing no `EFFECT_DENY` |
| `planResources.ignoreAlwaysAllow` | Plan entries whose filter is `ALWAYS_ALLOWED` |
| `planResources.ignoreAll` | Every plan entry; takes precedence over the other plan filter |

`ignoreAllowAll` cuts volume hard, and it removes the record that access was *granted*: the allow counts on the Insights charts, the activity rankings and any "who read this record" evidence all come from those same entries. Keep them when the audit trail is the point and take volume out elsewhere, for example `accessLogsEnabled: false`. Access entries are unaffected by these filters.

## Masking sensitive fields

Masks run at the PDP before an entry reaches the local buffer, so masked values never touch disk and never cross the network perimeter. Hub stores what it is sent — this is the only place the data can be removed.

Path syntax, worked examples for headers, tokens and PII, request-metadata handling, the silent failure mode to avoid, and how to verify a mask: [references/MASKING.md](references/MASKING.md).

## Reading the decisions back

Audit log search and the drill-through from a ranking, explaining a single allow or deny, the Insights charts and activity rankings, the usage dashboard, encrypted exports, retention and residency, and what to put in front of an auditor: [references/READING.md](references/READING.md).

## Debugging a decision that looks wrong

When an application allows or denies the wrong thing, the decision entry is the evidence: it records the request **as the PDP evaluated it**, so it shows what the PEP actually sent rather than what you believe it sent.

Work down the chain — did the request reach the PDP, are the logs on, what do the inputs say, which rule matched. Two facts settle most of the false starts: **`audit.enabled` defaults to `false`**, so there is usually nothing to read until it is set; and **using Cerbos Hub does not take stdout away**, since the storage driver and the audit backend are independent, and the Hub backend can pipe a redacted copy to a second backend anyway.

The ordered flow, the minimum configuration for each backend, `cerbosctl audit` and the `cerbosctl decisions` terminal UI, and a table of the usual causes: [references/DEBUG.md](references/DEBUG.md).

## Who can see it

Audit logs, Insights and Usage are visible to workspace **Owner** and **Analyst** roles only. Developer and Viewer do not see those tabs at all. Exporting is **Owner** only. Organization roles are inherited by every workspace except `Member`, which has to be granted workspace roles explicitly. Insights appears only once collection is enabled and decisions have started arriving. Full matrix: [user management](https://docs.cerbos.dev/cerbos-hub/user-management?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-user-management).

## Cerbos Synapse in front of the PDP

Behind Synapse the decision entry records the *enriched* request — what the PDP evaluated, not what the client sent.
Synapse adds `cerbos.dev/synapse/*` annotations plus any configured instance annotations, and for the in-process PDP the audit block nests under `pdp.inProcess`: [references/MASKING.md](references/MASKING.md#what-synapse-adds).

## References

- [references/MASKING.md](references/MASKING.md) — removing sensitive fields at the PDP: sections, path syntax, examples, metadata keys, verification, what Synapse adds to an entry
- [references/READING.md](references/READING.md) — audit log search, single-decision investigation, Insights, usage, exports, retention and compliance answers
