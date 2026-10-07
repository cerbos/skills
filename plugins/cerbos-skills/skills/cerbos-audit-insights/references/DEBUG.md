# Debugging a decision that looks wrong

The application allows something it should not, or denies something it should not. Work down the chain in this order — each step rules out everything above it, and most cases end at step 2 or 4.

## 1. Did the request reach the PDP?

Half of "Cerbos is denying everything" is a PEP that never called it, or called a different one. A deny-by-default engine and an unreachable engine look identical from the application.

- **Turn on access logs** (step 2) and make one request. An access entry per call means the PDP is being reached; no entry means it is not.
- **The PDP is up**: `GET /_cerbos/health` on the HTTP port returns 200.
- **The ports differ by protocol** — `3592` HTTP, `3593` gRPC. A gRPC client pointed at 3592 fails in a way that looks like a network problem.
- **Check what the client resolved.** A default `localhost` in a container reaches the container, not the PDP. In Kubernetes, confirm the service name and namespace.
- **Errors are not denials.** A transport failure, a timeout or a TLS mismatch must surface as an error your PEP handles, not as `false`. If the client swallows them into a deny, every outage looks like a policy bug — see the `cerbos-pep-integration` skill.

## 2. Turn the logs on

**`audit.enabled` defaults to `false`.** That single flag is the most common reason there is nothing to read. Access and decision logs are both enabled once it is on — `accessLogsEnabled` and `decisionLogsEnabled` default to `true`, and the generated configuration reference prints `false` for all three as an *example* value, not a default.

The fastest thing that works anywhere, including in a container where you just want to watch:

```yaml
audit:
  enabled: true
  backend: file
  file:
    path: stdout
```

**Using Cerbos Hub does not take stdout away.** The storage driver and the audit backend are independent settings: policies can come from a Hub deployment while decisions go to stdout, a file, or both. To keep Hub collection *and* watch locally, pipe the Hub backend to a second one:

```yaml
storage:
  driver: hub          # policies from Hub
  hub:
    remote:
      deploymentID: "..."
audit:
  enabled: true
  backend: hub         # decisions to Hub
  hub:
    storagePath: /var/cerbos/audit
    pipeOutput:
      backend: file    # ...and to stdout as well
      enabled: true
    file:
      path: stdout
```

Masks are applied before `pipeOutput`, so a piped copy is redacted the same way the Hub copy is.

For an interactive session rather than a stream, the `local` backend keeps records in an embedded store for seven days and makes them queryable:

```yaml
audit:
  enabled: true
  backend: local
  local:
    storagePath: /var/cerbos/audit
```

```bash
cerbosctl audit --tail=10                 # last ten records
cerbosctl audit --between=<from>,<to>     # an ISO-8601 window
cerbosctl decisions                        # a terminal UI over the decision log
```

`cerbosctl decisions` is the fastest way to find one request among many, and it is available whatever the policy source.

**Under Cerbos Synapse**, the same block nests under `pdp.inProcess.audit`. A top-level `audit:` section is ignored apart from `audit.instanceAnnotations`, and configuration that looks right and does nothing is almost always this.

## 3. Read the decision entry

A decision entry records the request **as the PDP evaluated it**, which is the point: it shows what the PEP actually sent, not what you believe it sent.

Read in this order:

1. **The inputs.** Is every attribute the condition reads present? An attribute the caller never sent is the single most common cause of an unexpected deny.
2. **The effect per action**, which is per action rather than per request — a partial allow across a batch is normal.
3. **The policy that matched.** Send `includeMeta: true` on the request and the response carries the matched policy and the effective derived roles, which tells you whether the rule you are thinking of is the rule that ran.

## 4. The usual causes, most common first

| What you see | Usual cause |
|---|---|
| Deny, and the condition looks correct | An attribute in the condition was absent from the request. A condition over a missing attribute is unsatisfied, not an error, so the rule simply does not match and deny-by-default takes over |
| Deny for a user who has the role | Role string mismatch — `admin` against `ADMIN`, or a role the IdP emits under a different claim |
| The policy change has no effect | The PDP is serving an older bundle. Under Hub, compare the build on the deployment's Decision points tab against the latest green build; otherwise check the store the PDP reads |
| Allow where a deny rule exists | The deny is on a different role than the one being evaluated. A deny beats an allow within a role, but a deny on one role does not block another role's allow |
| Right rule, wrong scope or version | The request's scope or policy version does not match the policy's. Check both in the decision entry |
| Intermittent or environment-specific | Two PDPs on different bundles, or one PDP reading a stale cache directory |

**Errors hiding as denials.** By default an error while evaluating a condition leaves the rule unsatisfied and evaluation continues, so a broken condition on a DENY rule silently stops denying. Turn on strict evaluation to make those errors deny instead, and re-run the case: a result that changes under strict evaluation is a condition that is erroring, not a policy that disagrees with you.

## 5. Synapse in the path

When the request passes through Synapse, the decision entry shows the inputs **after** proxy extensions ran. If an attribute is missing, the question is whether the extension that should supply it ran at all — `cerbos.dev/synapse/extensions` on the entry lists the extensions that processed the request, in order. An attribute present in the entry but absent from what the client sent was added by an extension, and one absent from both was never fetched.

## Reproducing it away from the application

Once the failing request is in front of you, replay it without the application in the loop: paste the principal, resource and action into a [Hub playground](https://docs.cerbos.dev/cerbos-hub/playground?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-playground), which shows an execution trace of every rule, condition and variable evaluated. For a local-only loop, `cerbos repl` evaluates conditions interactively — see the `cerbos-policy` skill, which owns policy-level debugging.
