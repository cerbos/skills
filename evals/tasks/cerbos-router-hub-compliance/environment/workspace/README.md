# Lendfield servicing platform

Lendfield services consumer loans for credit unions. Six backend services
(`accounts`, `payments`, `collections`, `documents`, `support-console`,
`reporting`) run on our own Kubernetes cluster (EKS, `prod` and `staging`).

Authorization runs on the open-source Cerbos PDP, deployed as a central
service in the `authz` namespace (`k8s/cerbos-pdp.yaml`, 4 replicas in prod).
Policies come from our `lendfield/authz-policies` repository through the PDP's
`git` storage driver; that part works well and nobody wants to change it.

The PDP's audit log is on and goes to stdout. Container stdout is kept on the
nodes for three days and nothing indexes it. A sample decision entry is in
`samples/decision-log.jsonl`.

The services pass the caller's identity as principal attributes, the Auth0
access token as auxiliary data (`auxData.jwt`), and our `x-session-token`
header for correlation. Customer records carry the customer's email address as
a resource attribute.

See `docs/auditor-request.md` and `docs/data-handling.md`.
