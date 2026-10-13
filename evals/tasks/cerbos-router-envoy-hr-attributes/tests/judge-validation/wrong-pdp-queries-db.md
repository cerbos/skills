# Gateway authorization by employment type

## Summary

Point Envoy's `ext_authz` filter directly at a Cerbos PDP and let the PDP read
employment type from the HR database through its Postgres driver. No custom
code is needed anywhere.

## Components

### Envoy → Cerbos PDP

Add `envoy.filters.http.ext_authz` to `gateway/envoy.yaml` with a gRPC service
pointing at the PDP's port 3593. The PDP implements Envoy's external
authorization API natively, so the request path, method and the `x-jwt-payload`
header arrive as the resource and principal.

### PDP reading the HR database

Configure the PDP with
`storage.driver: postgres` and `storage.postgres.url:
postgres://hr-replica.internal:5432/hr`. Besides policies, the Postgres driver
exposes tables to CEL, so a policy can read the caller's row:

```yaml
condition:
  match:
    expr: db.query("select employment_type from people where okta_user_id = $1", P.id)[0].employment_type == "contractor"
```

Employment type therefore never has to be in the token or passed by anyone.

### Policies

A `route` resource policy: employees allow all; contractors denied on `finance`
and `hr`; interns `read` only; inactive denied. Tests cover each type, with a
test database fixture.

### Delivering rule changes

Keep the policies in git and let the PDP's git watcher pick up changes, so
restricting `/deploy/` for contractors next quarter is a pull request and no
redeploy. Because the PDP reads the HR replica live, a person who converts from
contractor to employee gets the new access on their next request.

## Approaches to avoid

- Changing the 40 services or adding middleware to them: the gateway already
  sees every request.
- Putting employment type in tokens: the identity team won't do it, and it
  would go stale when someone converts or leaves.
- Adding extra components between Envoy and the PDP; every hop adds latency.

## Next steps

1. Create a read-only Postgres user for the PDP.
2. Configure the PDP Postgres driver and write the policy.
3. Add the `ext_authz` filter to Envoy with `failure_mode_allow: false`.
4. Roll out to dev, staging and prod.
