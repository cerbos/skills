# Access trail for the SOC 2 audit

## Recommendation

Turn on **Cerbos Hub audit log collection** on the PDPs we already run. Each
PDP switches its audit backend from `file` (stdout) to `hub`: it buffers every
decision and access entry on a local volume and streams it to Cerbos Hub,
where it is searchable, charted in **Insights**, and exportable. **Masks**
applied at the PDP delete email addresses and the session token from every
entry before it is buffered or sent, so that data never leaves our network.

This gives the auditor a searchable record without us building or running a
log stack.

## What changes and what stays the same

Stays the same:

- The four PDP replicas keep running in the `authz` namespace on our cluster
  and keep evaluating every check there. Hub receives audit entries only; it
  does not run our PDPs or see requests before they are decided.
- Policies keep coming from `lendfield/authz-policies` through the `git`
  storage driver. Nothing in the policies changes. (Moving policy delivery to
  Hub later is an option, not a prerequisite.)
- The six services and their Cerbos calls do not change.

Changes, all in `k8s/cerbos-pdp.yaml`:

```yaml
# hub.credentials come from CERBOS_HUB_CLIENT_ID / CERBOS_HUB_CLIENT_SECRET
# (a Kubernetes secret) and CERBOS_HUB_PDP_ID (the pod name)
audit:
  enabled: true
  includeMetadataKeys: ["x-request-id"]   # stop capturing x-session-token
  backend: hub
  hub:
    storagePath: /var/cerbos/audit        # persistent volume, not emptyDir
    mask:
      metadata:
        - "['x-session-token']"
      checkResources:
        - inputs[*].principal.attr.email
        - inputs[*].resource.attr.email
        - inputs[*].auxData
      planResources:
        - input.principal.attr.email
        - input.resource.attr.email
        - input.auxData
```

- The credential is a **Read & write** client credential on a Hub deployment
  (read-only cannot upload logs), stored as a Kubernetes secret.
- The Deployment becomes a StatefulSet (or gets a PVC per replica) so the
  buffer survives restarts; entries are deleted only after Hub acknowledges
  them.
- Principal and resource IDs (`auth0|6512`, `cus_88213`) stay: they are not
  personal data under DH-7, and they are what makes the record answer "who
  accessed which customer".

## The auditor's four points

1. **Searchable record.** Hub **Audit logs → Decision logs** filters by time
   range, principal, resource kind, action and allow/deny. "Who viewed
   `cus_88213` in December" is a filter.
2. **Why it was permitted.** Each decision entry shows the effect per action
   and the policy that produced it, linked to the policy, plus the roles and
   attributes it was evaluated on. Services can add a ticket ID as a
   `requestContext.annotations` entry later if the auditor wants a business
   reason too.
3. **Monitoring.** **Insights** charts hourly and daily allows and denies and
   ranks the most active principals and resource-action pairs, with
   drill-through to the decisions. A support agent viewing far more profiles
   than usual tops the `customer:view_profile` ranking; a deny spike shows on
   the charts. We review it weekly and record the review.
4. **Retention.** Hub keeps the logs for its retention period; a monthly
   age-encrypted **export** to our own S3 bucket covers the whole observation
   period regardless.

Data handling: DH-3 and DH-4 are met because masks remove the emails, JWT
claims and session token at the PDP; masked fields are deleted, not
redacted, and never written to the buffer.

## Avoid

- Running ELK or Loki ourselves for this: we have no one to operate it.
- Masking anywhere after the PDP — Hub stores what it receives.
- `decisionLogFilters.checkResources.ignoreAllowAll`: it would drop the
  allowed-access evidence the auditor asked for.

## Next steps

1. In the Hub console, create a policy store mirroring `authz-policies` and a
   `prod` and `staging` deployment, and generate a **Read & write** client
   credential on each; store them as Kubernetes secrets (cerbos-hub-setup).
2. Write the masks and metadata change above (cerbos-audit-insights).
3. In staging, enable the `hub` backend with `pipeOutput` to stdout, drive
   requests, and confirm the piped entries contain no email and no
   `x-session-token`; confirm entries arrive in Hub.
4. Add the persistent volume for `storagePath`.
5. Roll out to prod before 1 November; confirm all four PDPs appear and
   decisions arrive.
6. Give the auditor Analyst access, set up the monthly export, and walk them
   through search and Insights.
