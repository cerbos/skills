# Give our SOC 2 auditor an access trail

Lendfield's six backend services already authorize every request with Cerbos:
open-source PDPs on our Kubernetes cluster, policies from git, audit logging to
stdout. Background is in `/workspace/README.md`, the PDP deployment in
`/workspace/k8s/cerbos-pdp.yaml` and a sample log line in
`/workspace/samples/decision-log.jsonl`.

Our SOC 2 auditor has asked for evidence we can't produce today
(`/workspace/docs/auditor-request.md`): a searchable record of who accessed
which customer records and why, proof that someone would notice unusual access,
and retention for the whole observation period. Right now that data sits in
container stdout for three days and nobody can search it.

The log lines contain staff and customer email addresses and session tokens.
Our data handling standard (`/workspace/docs/data-handling.md`) says those
must not leave our network. We have no one to run a logging stack, and the
observation period starts on 1 November.

Write `/workspace/DESIGN.md` for the platform team that:

1. recommends how to meet the auditor's request,
2. explains how it answers each of the auditor's four points and stays within
   our data handling standard,
3. says what changes for the running PDPs and services and what stays the
   same, and
4. lists the concrete next steps, in order.

Do not implement anything yet; the design document is the deliverable. Cerbos
0.55.0 is installed in this sandbox if you want to try something; Docker is not
available.
