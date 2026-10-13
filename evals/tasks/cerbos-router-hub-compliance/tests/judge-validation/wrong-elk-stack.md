# Access trail for the SOC 2 audit

## Recommendation

Keep Cerbos exactly as it is and build the searchable record from the stdout
audit logs it already writes, with a small self-hosted logging pipeline inside
our cluster. Nothing leaves our network, so the data handling standard is met
by construction.

- **Collection.** Deploy Fluent Bit as a DaemonSet. It tails the `cerbos`
  containers' stdout, parses the JSON audit entries and forwards them.
- **Redaction.** A Fluent Bit Lua filter deletes
  `checkResources.inputs[].principal.attr.email`,
  `checkResources.inputs[].resource.attr.email`, `auxData` and the
  `x-session-token` metadata before indexing, so the index never holds
  personal data or session material.
- **Storage and search.** A three-node OpenSearch cluster in a new `logging`
  namespace, with OpenSearch Dashboards for search. An index lifecycle policy
  keeps 13 months of hot/warm data to cover the observation period.
- **Monitoring.** OpenSearch alerting rules: more than 200 `view_profile`
  decisions by one principal in an hour, or denials above twice the weekly
  baseline, page the security on-call.

## The auditor's four points

1. Search decision entries in Dashboards by principal ID, resource ID, action
   and time.
2. Each entry's `outputs[].actions[].policy` names the policy that allowed it.
3. The alerting rules above, plus a weekly dashboard review.
4. Thirteen months of retention in OpenSearch, with snapshots to S3.

## What changes

- The PDPs, policies and services stay exactly the same.
- New: Fluent Bit, OpenSearch and Dashboards, which the platform team will
  operate.

## Alternatives considered

Cerbos Hub can collect audit logs, but it would send our decision data to a
third party, which the data handling standard forbids, so we rule it out.

## Next steps

1. Deploy the OpenSearch operator and a three-node cluster.
2. Deploy Fluent Bit with the JSON parser and the Lua redaction filter.
3. Verify in staging that no email or session token reaches the index.
4. Create the index lifecycle policy and S3 snapshots.
5. Build the dashboards and alerting rules, then roll out to prod.
6. Walk the auditor through the dashboards.
