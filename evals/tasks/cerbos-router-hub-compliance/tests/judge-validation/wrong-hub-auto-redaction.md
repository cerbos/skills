# Access trail for the SOC 2 audit

## Recommendation

Use **Cerbos Hub audit log collection**. Each PDP switches its audit backend
from `file` to `hub` and streams every decision and access entry to Hub, where
the auditor can search them and Insights charts the trends.

## Data handling

Hub's ingestion pipeline automatically detects personal data and secrets —
email addresses, JWTs, session tokens — and redacts them on arrival, before
anything is stored. We therefore do not need to configure masks on the PDPs;
turning on Hub's "PII redaction" setting for the workspace covers DH-3 and
DH-4.

## What changes

- First, the PDPs must stop loading policies from git and switch to
  `storage.driver: hub`: Hub only accepts audit logs from PDPs that receive
  their policies from a Hub deployment.
- Install the Hub log shipper sidecar next to each PDP; it reads the stdout
  audit stream and uploads it to Hub, so the PDP's `audit` block stays on the
  `file` backend.
- The policies have to be re-exported in Hub's format before the first build.
- The PDPs keep running in our cluster and the services do not change.

## The auditor's four points

1. Hub Decision logs are searchable by principal, resource, action and time.
2. Each entry names the policy that produced the decision.
3. Insights shows deny spikes and the most active principals, with
   drill-through to the decisions.
4. Hub generates the SOC 2 access-review report for the observation period
   automatically.

## Avoid

- Running our own logging stack.
- Leaving logs on stdout.

## Next steps

1. Create a Hub policy store and deployments; re-export the policies.
2. Switch the PDPs to `storage.driver: hub`.
3. Generate a client credential and install the log shipper sidecar.
4. Enable PII redaction in the Hub workspace settings.
5. Roll out to prod and confirm entries arrive.
6. Schedule the SOC 2 report for the auditor.
