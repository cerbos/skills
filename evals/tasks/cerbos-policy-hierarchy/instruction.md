# Scoped report policies

Use the installed `cerbos-policy` skill. Requirements and ALLOW/DENY effects below
are confirmed; proceed with implementation. Cerbos 0.55.0 is installed directly
in this sandbox. Docker is unavailable inside the sandbox, so use the native
`cerbos` binary for compilation and tests.

Create a Cerbos policy bundle under `/workspace/policies` for resource kind
`report`, version `default`, organized as a policy hierarchy. Each request
carries the report's scope: no scope, `acme`, `acme.eu`, or `globex`.

Principals have a string attribute `region`. Reports have a string attribute
`status` (`draft`, `published`, or `archived`) and an optional boolean
`contractor_visible`; absence means false.

**Base policy.** Applies to requests without a scope and is inherited by every
scope unless changed below. Viewers read reports, editors maintain them, and
admins manage their lifecycle: `viewer` may `view`; `editor` may `view` and
`edit`; `admin` may `view`, `edit`, and `delete`. All other roles and actions are
denied.

**`acme`.** Acme's compliance team requires that every Acme-level policy can only
narrow the permissions of the level above it: an ALLOW rule at an Acme level must
never grant access that its parent level denies. Within `acme`, editors may edit
only `draft` reports so published work stays stable; admins are unaffected.
Everything else is inherited.

**`acme.eu`.** The same narrowing-only guarantee applies. For EU data residency,
every permission in `acme.eu` additionally requires the principal's `region` to
be `eu`. The `acme` restrictions still apply.

**`globex`.** Globex manages its own exceptions and may grant or revoke
permissions independently of the base policy. Contractors (`contractor`) may
`view` reports whose `contractor_visible` is true, so Globex can share selected
work with outside staff. Nobody, including admins, may `delete` Globex reports,
because Globex retains every report. Everything else is inherited from the base
policy; Acme's restrictions do not apply to Globex.

A principal with several roles receives every permission that any of its roles
would receive in that scope.

Use these paths:

- `resource_policies/report.yaml` (base policy, no scope)
- `resource_policies/acme/report.yaml`
- `resource_policies/acme/eu/report.yaml`
- `resource_policies/globex/report.yaml`

Supply native Cerbos tests under `resource_policies/` with reusable fixtures in
`resource_policies/testdata/principals.yaml` and
`resource_policies/testdata/resources.yaml`. The tests must actively cover each
scope: inherited base permissions, the Acme draft restriction in both Acme
scopes, the EU region requirement, contractors denied outside Globex even for
contractor-visible reports, Globex contractor visibility (including an absent
flag), the Globex delete ban for admins, Acme's restriction not applying to
Globex, and a principal with several roles. Compile and run the tests in normal
and strict evaluation modes. The bundle must be self-contained.
