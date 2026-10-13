# Gateway authorization by employment type

## Summary

Use a Cerbos PDP for the decisions and a small shared authorization middleware
in each service to supply the employment type. Envoy keeps validating tokens
and forwards the verified payload in `x-jwt-payload`.

## Components

### Cerbos PDP

Run the PDP as a central service in each environment, reading policies from our
git repository. Write a `route` resource policy: employees may do anything,
contractors may not touch the `finance` or `hr` prefixes, interns may only
`read`, inactive people are denied. Policy tests cover each type.

### Shared middleware (`authz-middleware`)

Publish a small library for Go, Java and Python. On each request it:

1. reads `sub` from `x-jwt-payload`;
2. queries the HR read replica:
   `select employment_type, active from people where okta_user_id = $1`,
   caching for 60 seconds;
3. calls the PDP's `CheckResources` with the principal attributes
   `employment_type` and `active`, resource kind `route` with the path prefix,
   and the action from the HTTP method;
4. returns 403 on a deny.

Each of the 40 services adds the middleware to its router. This keeps the
gateway simple and avoids running any extra components between Envoy and the
PDP. The services already have database drivers, so the HR lookup is a few
lines.

### Why not at the gateway

Envoy has no way to query Postgres, and the PDP cannot either, so the lookup
has to happen in application code. Adding it to each service is the least
infrastructure.

## Approaches to avoid

- Hard-coding the rules in each service: the rules live in Cerbos policies.
- Adding employment type to tokens: the identity team won't do it.

## Next steps

1. Write the policy and tests.
2. Deploy the PDP.
3. Build and publish `authz-middleware` for Go, Java and Python.
4. Roll it out to the 40 services, starting with finance and hr.
