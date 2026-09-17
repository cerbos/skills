# Reading the collected decisions

Everything here is the Cerbos Hub console, fed by PDPs with the `hub` audit backend enabled. All times on these pages are UTC.

## Audit logs

The workspace's **Audit logs** tab holds **Decision logs**, **Access logs** and **Exports**.

**Decision logs** list one row per entry with the timestamp, call ID, request kind (`CheckResources` or `PlanResources`), principal ID, resource kind, resource ID and the action decision. Toggle between the **Decision** view for the compact summary and the **JSON** view for the raw entry. Filter by time range, PDP ID, policy source, principal, resource kind, action or policy decision.

Clicking a row opens the details panel:

- **Principal** — ID, roles, effective derived roles, attributes
- **Resource** — kind, ID, scope, attributes
- **Decisions** — the effect per action and which policy produced it, each policy name a link straight into that policy in the policy store
- **Outputs** — values returned by policy rules
- **Raw JSON** — the complete entry

**Access logs** record every API request the PDP received, including ones that were invalid or unauthenticated and so never reached a decision. Filter by PDP and time range. A valid `CheckResources` or `PlanResources` call has a decision entry with the same call ID.

## Explaining one allow or deny

1. Get the `cerbosCallId` from the calling application's own logs — Cerbos returns it on every response, which is what joins the two sides together.
2. In **Decision logs**, narrow to the principal, resource kind and time window around the request, and find the entry.
3. Open it and read **Decisions**: the effect for the action in question and the policy that produced it. Follow the policy link to the rule.
4. Read the recorded attributes and effective derived roles to see the inputs the condition was evaluated against. An unexpected deny is usually a missing attribute or a role that was not derived, both visible here.
5. No decision entry, only an access entry? The request never got as far as evaluation — check the status code and peer on the access entry.

On a PDP using the `local` backend instead, the same investigation runs from the shell: `cerbosctl audit --kind=decision --lookup=<callID>`, `--tail=N`, `--since=3h` or `--between=<from>,<to>`, and `cerbosctl decisions` for a browsable text interface.

## Insights

Built from the decisions already arriving — nothing extra to configure once collection is on.

| Visualization | Window | Shows |
|---|---|---|
| Hourly decisions | last 7 days | Stacked allows and denies per hour, with an Allowed / Denied / Combined toggle. Best for short-lived spikes, such as a burst of denials after a deployment. |
| Daily decisions | last 30 days | The same breakdown per day, smoothing hourly noise. Best for trends. |
| Daily active principals | last 30 days | Distinct principals making requests each day. Adoption, seasonality, unexpected drops. |
| Most active principals | last 30 days | Top principal IDs by request count. |
| Most active resource kinds | last 30 days | Top kinds by request count — which parts of the application are being checked. |
| Most active resource & action pairs | last 30 days | Kind-and-action combinations, e.g. `document:view` against `document:delete`. |

Every ranking row carries a **View** link that opens the audit log pre-filtered to that principal, resource kind, or resource-and-action pair. That drill-through is the intended route from "this looks wrong" to the individual decisions behind it, without rebuilding the filter by hand.

Reading a swing in the deny ratio: a policy change stricter than intended, a misconfigured client, or an application bug such as a typo in a resource or action name.

## Usage dashboard

Monthly rather than operational. Summary metrics for the current month, each against the previous one: **Active principals**, **Decisions** (Check API — one call can check several actions, so this exceeds the call count) and **Query plans**. Trend charts break Check calls into allowed and denied, and Plan calls into allowed, denied and conditional. A month-by-month table sits underneath. At organization level the dashboard aggregates every workspace.

Insights answers "what is happening now"; Usage answers "how much, month over month".

## Exports

Requires the **Owner** role. Not available for on-premises deployments, where the data is already in your own infrastructure.

Apply the filters and time range you want on **Decision logs** or **Access logs**, then **Export**. The dialog confirms the filters and lets you adjust the range; with no range selected it defaults to the last 24 hours. **Add to export queue** starts it in the background and the **Exports** tab tracks progress — no need to keep the page open. A workspace can only start so many exports per hour; each one stops counting towards the limit an hour after it was created.

Every export is encrypted with [age](https://age-encryption.org). Supply the public half of your own key pair (it begins with `age1`), or leave the field blank and Hub generates a pair and shows it once. **Hub does not retain the secret key and cannot reissue it** — lose it and the only remedy is a fresh export.

The download is age-encrypted, gzipped JSON Lines, one object per entry:

```bash
age -d -i age.key <exported-file> | gunzip
```

That pipes straight into `jq`, a data warehouse or a SIEM with no conversion. Exported files stay downloadable for seven days and are then deleted; the underlying entries are untouched, so the export can be recreated while they remain within retention.

## Retention, residency and access

- **Hub cloud** stores audit logs in Cerbos-managed infrastructure in the Netherlands (GCP `europe-west6`), retained according to the plan's retention policy.
- **On-premises** stores them in a ClickHouse instance in your own infrastructure; residency, retention and access are yours. See [on-premises deployments](https://docs.cerbos.dev/cerbos-hub/on-premises.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-audit-insights).
- Deleting an organization permanently deletes its audit logs along with everything else.
- For continuous forwarding into an existing SIEM or UEBA pipeline, configure the `pipeOutput` secondary backend on the PDP rather than exporting repeatedly.

## Compliance questions

The Cerbos documentation names SOC 2, ISO 27001, HIPAA, PCI DSS and GDPR as the audit requirements aggregated decision logs are there to serve. What to reach for:

| The question | Answer from |
|---|---|
| "Show every access to this kind of record over the quarter" | Decision logs filtered by resource kind, principal and time range; or a ranking's **View** drill-through |
| "Why was this specific request allowed?" | The call ID from the application, then the entry's Decisions panel and the policy it links to |
| "Prove denials are enforced" | Deny series on the decision charts, plus individual entries naming the policy that denied |
| "Who can read the audit trail?" | The Owner and Analyst roles only, export Owner only — the roles section of the skill has the detail |
| "How do you minimise the personal data you retain?" | Masks remove fields at the PDP before the entry is buffered or transmitted — see [MASKING.md](MASKING.md) |
| "Where does the data live and for how long?" | Residency and retention above |
| "Hand our auditor the evidence" | An encrypted export as JSON Lines, or `pipeOutput` into the systems the auditor already reads |
| "Correlate with our application logs" | `cerbosCallId`, logged on both sides |

Canonical references: [audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-audit-insights), [Insights](https://docs.cerbos.dev/cerbos-hub/insights.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-audit-insights), [usage dashboard](https://docs.cerbos.dev/cerbos-hub/usage-dashboard.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-audit-insights), [user management](https://docs.cerbos.dev/cerbos-hub/user-management.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-audit-insights), [cerbosctl](https://docs.cerbos.dev/cerbos/latest/cli/cerbosctl.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-audit-insights).
