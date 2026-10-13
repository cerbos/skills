# Managers can't approve invoices

Since this morning's release, managers have been reporting that they can't
approve invoices: every approval comes back 403 Forbidden, including invoices in
cost centres they manage and well under their approval limit. Employees can
still see their own invoices, and managers can still open invoices. Nobody has
touched the authorization policy in weeks, and finance will not accept a fix
that weakens it: managers may only approve submitted invoices in the cost
centres they manage, up to their approval limit, and never their own.

Find the root cause and fix it.

What is on this host:

- The invoice service, a Python app in `/workspace/app` (see its `README.md`).
  It listens on port 8000 and calls the Cerbos PDP over HTTP using the Cerbos
  Python SDK, which is already installed. It reads `PORT`, `CERBOS_URL`,
  `INVOICES_FILE` and `APP_JWT_SECRET` from the environment; keep those working.
- The authorization policies in `/workspace/policies`. Do not change them.
- The PDP configuration in `/workspace/cerbos/config.yaml`. The PDP has audit
  logging switched on, and the decisions from this morning's failed approvals
  are in `/var/log/cerbos/audit.log`.
- Cerbos 0.55.0, installed natively (`cerbos` on the PATH). Docker is not
  available. Neither the PDP nor the app is running at the moment; start them as
  the README describes if you need them.

The web UI depends on the JSON the service returns, so do not change the shape
of its responses.

When you are done, write a short `/workspace/FINDINGS.md` for the team: the root
cause, the evidence that pointed to it, and what you changed.
