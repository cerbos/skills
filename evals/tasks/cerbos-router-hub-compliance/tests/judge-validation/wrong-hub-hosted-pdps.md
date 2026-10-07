# Access trail for the SOC 2 audit

## Recommendation

Move authorization onto **Cerbos Hub's managed PDPs** and turn on Hub audit
log collection. Hub runs the PDPs for each deployment in its cloud and
evaluates every check there, so it records every decision centrally with no
log pipeline on our side.

- Create a Hub policy store mirroring `authz-policies`, with `staging` and
  `prod` deployments. Hub compiles and tests every change.
- Point the six services' Cerbos clients at the deployment's hosted PDP
  endpoint instead of the `cerbos` service in the `authz` namespace, then
  scale our PDP Deployment to zero.
- Configure masks in the Hub workspace (**Settings → Audit masking**) for
  `principal.attr.email`, `resource.attr.email`, `auxData` and the
  `x-session-token` header; Hub strips them when it stores each entry.

## The auditor's four points

1. Hub **Audit logs → Decision logs** filters by principal, resource kind,
   action, decision and time range.
2. Each entry shows the effect and the policy that produced it.
3. **Insights** charts allow and deny trends and the most active principals,
   with drill-through.
4. Retention per Hub's retention period, plus monthly encrypted exports to S3.

## What changes

- The PDPs no longer run in our cluster; the services call Hub over the
  internet with a client credential.
- The policies themselves are unchanged.

## Avoid

- Running ELK or Loki ourselves.
- `ignoreAllowAll` decision log filters.

## Next steps

1. Create the store, deployments and client credentials.
2. Configure the audit masks in the Hub workspace settings.
3. Switch staging services to the hosted endpoint and check the masked
   entries in Hub.
4. Switch prod services, then remove our PDP Deployment.
5. Give the auditor Analyst access and walk them through search and Insights.
