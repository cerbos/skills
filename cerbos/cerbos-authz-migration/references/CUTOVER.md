# Shadow mode and cutover

Phases 5 and 6. The old system stays authoritative until the diff is clean, then each resource kind flips one at a time and the old path is deleted.

## The shim

At every guard site, run both checks, record both answers, return the legacy one.

```
function can(principal, action, resource):
    legacy = <the existing check, unchanged>

    if shadow_enabled(resource.kind):
        try:
            cerbos = cerbos.checkResource(principal, action, resource)
        except:
            cerbos = ERROR                      # never propagate
        record(correlation_id, principal, action, resource, legacy, cerbos)

    if enforce_cerbos(resource.kind):
        return cerbos
    return legacy
```

Four properties are non-negotiable:

- **The legacy answer is returned** until the flag for that resource kind flips. Shadow mode that changes behaviour is not shadow mode.
- **Cerbos failures never propagate.** A timeout or a connection error is recorded as `ERROR` and the request proceeds on the legacy answer. During shadow, an unavailable PDP must be invisible to users.
- **The flag is per resource kind**, so the cutover is granular and a rollback affects one kind rather than the whole application.
- **Both answers are recorded together**, with enough context to reproduce the call.

Where a `can()` helper already exists, this is a one-file change and every caller comes along for free. Where guards are scattered inline, introduce the helper first — that refactor is worth doing on its own, and it is far safer than editing forty call sites twice.

`cerbos-pep-integration` ([API](https://docs.cerbos.dev/cerbos/latest/api/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-api)) owns the SDK call and the request construction.

## What to record

One row per comparison:

| Field | Why |
|---|---|
| Correlation ID | Joins the application-side record to the Cerbos audit entry |
| Principal ID and roles | The first thing you check when a decision surprises you |
| Resource kind, ID, and the attributes sent | Disagreements are usually a missing attribute; you cannot see that without the list |
| Action | |
| Legacy effect | allow / deny |
| Cerbos effect | allow / deny / error |
| Agreement | allow, so the common case aggregates to a single number |
| Guard site | `file:line`, matching the inventory's Source column, so a diff points at a rule |

Log only on disagreement plus a sample of agreements, not every call. A busy service produces a volume nobody reads, and the sample is enough to prove the shadow path is actually running.

## The Cerbos half, for free

Turn on Hub [audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_hub-audit-log-collection) and the Cerbos side of every comparison is already recorded: the principal with roles and attributes, the effective derived roles, the resource with its attributes and scope, the effect per action, the matched policy, and any rule outputs. Policy names in an entry link through to the policy in the store.

That is the entire right-hand column of the diff, with the evaluation detail attached — which matters because the interesting question is never *what* Cerbos decided but *why*. Building an equivalent decision log by hand, during the riskiest weeks of the project, is work with no lasting value.

The [Insights](https://docs.cerbos.dev/cerbos-hub/insights?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_hub-insights) view aggregates the same data: allow/deny volume per hour and per day, active principals, and the busiest resource-and-action pairs. During shadow it answers "is the shadow path actually being exercised, and by how much"; after each flip it is where a swing in the deny ratio shows up first. Querying both is `cerbos-audit-insights` ([Audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_hub-audit-log-collection)).

Your application-side record then only needs the legacy effect and the correlation ID. Keep the PDP ID distinct for the shadow fleet so shadow traffic is separable from anything already in production.

## Reading the diff

Report weekly, per resource kind:

```
orders          calls 41,208   agree 41,166 (99.90%)
  cerbos DENY / legacy ALLOW    31   → 2 causes, both open
  cerbos ALLOW / legacy DENY     9   → 1 cause, fixed Tue, awaiting confirmation
  cerbos ERROR                   2   → PDP restart during deploy
```

Group by cause, never by count. Thirty disagreements from one missing attribute is one finding; three disagreements from three different rules is three, and considerably worse news.

### Triage

**Cerbos DENY, legacy ALLOW.** In order of likelihood:

1. **A missing request attribute.** The condition referenced something the PEP did not send, so it could not hold. By default a condition that errors leaves the rule unsatisfied and evaluation continues — which silently skips the rule rather than failing loudly. Run the policy suites under strict evaluation, where such errors deny instead, to surface these during development rather than in the diff.
2. **A rule missed in Phase 1.** Usually an implicit grant: a branch that returned early, a default case, a superuser short-circuit.
3. **A role name mismatch.** Roles and derived role `parentRoles` are case-sensitive, and the string the IdP issues is not always the string the old code compared against.
4. **A derived role that did not activate.** Check that it is imported with `importDerivedRoles`, that a rule names it in `derivedRoles`, that the principal holds one of its `parentRoles`, and that its condition holds. `includeMeta` on the request returns the effective derived roles, which settles it immediately.
5. **The legacy system was wrong.** It permitted something it should not have. Verify against the intent in the inventory before "fixing" the policy — this outcome is the migration paying for itself, and treating it as a defect undoes that.

**Cerbos ALLOW, legacy DENY.** More serious, because it is a potential over-grant:

1. **An implicit deny not captured.** An early return, an exception path, a filter applied upstream of the guard, a check in a layer nobody grepped.
2. **A wildcard that matched too much.** `actions: ["*"]` or `roles: ["*"]` written to summarise several rules and quietly covering more.
3. **Multi-role allow-wins.** The legacy code read a single role field; the principal now carries several and one of them grants. Expected behaviour, and a genuine behaviour change — confirm it is wanted.
4. **A deny that never fires.** A `EFFECT_DENY` rule whose condition errors at runtime is skipped, so the action falls through to an allow. This is the most dangerous failure mode in a Cerbos policy and the reason to run the suites under strict evaluation.

**Same input, different verdicts on different calls.** A time-dependent condition, or the two sides reading state at different moments — the legacy check running before an update and the Cerbos check after it.

**Cerbos DENY on everything for one resource kind.** No policy for that kind or that policy version, or the request carries a scope with no matching policy file. Cerbos is deny-by-default and has no "no opinion" state, so an absent policy denies rather than abstaining.

**Cerbos ERROR.** Not a policy problem. Connectivity, PDP restarts, or a request the PDP rejected — a schema violation under `reject` enforcement denies every action, which looks like a policy bug and is not.

### Closing a finding

Every fix follows the same loop, and the middle step is the one people skip:

1. Fix the policy, or the attributes the PEP sends.
2. **Add the case to the test suite**, named after the inventory row's Source. This is what stops a closed disagreement reopening.
3. Redeploy and confirm the disagreement stops appearing in the next report.

With a Hub policy store the loop is minutes: upload, Hub compiles and runs every suite in the store, and a green build reaches every connected PDP within seconds. A failing suite blocks the bundle and leaves the previous one live, so a bad fix cannot reach the shadow fleet. `cerbos-hub-setup` ([Hub getting started](https://docs.cerbos.dev/cerbos-hub/getting-started?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_hub-getting-started)) covers the store and deployment; `cerbos-policy` ([Testing policies](https://docs.cerbos.dev/cerbos/latest/policies/compile?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-policies-compile)) owns the upload command and the suite format.

## Exit criterion

A full business cycle of traffic with zero unexplained disagreements.

"Full business cycle" is specific to the system and worth naming explicitly before the period starts: a month-end close, a billing run, a quarterly report, the batch job that only runs on the first Monday, an on-call escalation using the admin path. Rare code paths carry the rules nobody remembers, and they are exactly the rules Phase 1 missed. A week of weekday traffic proves very little about them.

Every remaining difference is a recorded, deliberate decision — an intentional behaviour change, or a gap-register item with an owner.

## Rolling out

Per resource kind, in the Phase 2 grouping order, simplest first:

1. **Flip.** `enforce_cerbos` returns true for that kind. The legacy check keeps running as the shadow, so the comparison continues in the other direction.
2. **Watch.** Decision volume and allow/deny ratio for that kind, for at least a full day of normal traffic. A swing in the deny ratio is the earliest signal that something moved that should not have.
3. **Delete.** Remove the legacy check, its helpers, and any permission tables it depended on that nothing else reads.
4. **Next kind.**

Step 3 is not a follow-up ticket. Code left behind is a second source of truth, and the next engineer will edit it instead — which is the exact failure the migration exists to remove. A migration that stops after step 2 has added a system rather than replaced one.

## Rollback

Two levers. Test both before the first flip, because a rollback path that has never been exercised is not a rollback path.

| Lever | Undoes | Reach |
|---|---|---|
| The `enforce_cerbos` flag | Returns one resource kind to the legacy decision | Instant, one kind, requires the legacy code to still be there — which is why deletion trails the flip |
| Hub deployment freeze or rollback | Pins every connected PDP to a known-good bundle | Seconds, fleet-wide, no application deploy |

[Freezing](https://docs.cerbos.dev/cerbos-hub/deployments?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_hub-deployments) holds the live bundle in place while you diagnose; rolling back promotes an earlier build and freezes the deployment so the next policy change does not silently undo it. Every build records the contributing stores and their versions, so "which policies were live at 14:20" is answerable rather than reconstructed.

Once a kind's legacy code is deleted, the flag is gone and the deployment lever is the only one left. That is the right end state; reaching it deliberately, one kind at a time, is the point of the sequence.

## Reporting the finish

When the last guard is gone:

- Rows migrated, against the Phase 2 inventory, by resource kind.
- Gap-register items, each with the option taken and who decided.
- Rules deliberately dropped, with reasons.
- Unguarded entry points found in Phase 1 and what was done about each.
- Behaviour changes users may notice — a `404` that became a `403`, an error message that changed, a multi-role case that now grants where it used to refuse.

The last item is the one that generates support tickets. Write it before the tickets arrive.
