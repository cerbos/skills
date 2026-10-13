# Ledgerly authorization design

## Summary

Use Cerbos Hub with an embedded PDP in the React app. Every permission decision
is made in the browser by the Cerbos WebAssembly engine, from policies managed
in Hub, so the UI and the rules can never disagree and the API gets simpler.

## Components

### Policies with tenant scopes

Write a base `invoice` resource policy for the default rules and one scoped
policy per customer that differs: `scope: acme` (approver role above $10,000,
no deleting sent invoices) and `scope: globex` (clerks approve up to $5,000).
New customer variations are new scoped policy files, with tests.

### Cerbos Hub

Mirror the policy repo into a Hub policy store with deployments for dev,
staging and prod. Hub compiles and tests every change and publishes the bundle.

### Embedded PDP in React

Create an ePDP rule on each deployment with dynamic scopes, so each browser
downloads only its tenant's scope. In React, construct one `Embedded` client
from `@cerbos/embedded-client` and wrap the app in `CerbosProvider` from
`@cerbos/react`. Buttons use `useCheckResource`; before calling the API, the
click handler checks `isAllowed` again and only sends the request when Cerbos
allows it.

### API

Because the Cerbos engine already evaluated the official policies before the
request was sent, the API does not need to call a PDP. It keeps the tenant
filter on queries and forwards the request. This removes the PDP from the
request path entirely, which keeps latency down, and the security review's
endpoints are now covered because the browser will not send a request Cerbos
denies.

## Approaches to avoid

- Hard-coded role checks in React or Express.
- Running and operating a PDP fleet for the API when the ePDP already decides.

## Next steps

1. Write the policies and tests.
2. Set up Hub, the deployments and the ePDP rule.
3. Wire `@cerbos/embedded-client` and `@cerbos/react` into the web app.
4. Remove the old `if` statements from the API routes.
