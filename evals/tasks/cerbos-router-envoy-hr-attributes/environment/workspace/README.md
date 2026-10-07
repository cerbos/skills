# Internal platform

About 40 internal HTTP services (Go, Java and a few Python) sit behind one Envoy
gateway (`gateway/envoy.yaml`). Envoy validates Okta access tokens with its
`jwt_authn` filter and routes by path prefix. Okta tokens carry only `sub`
(the Okta user ID) and `email`; there is no group or employment claim, and the
identity team will not add HR data to tokens.

Employment data lives in the HR database (Postgres 16, `hr/schema.sql`), owned
by the HR systems team. It is the source of truth for whether someone is an
employee, a contractor or an intern, and changes when people convert or leave.

Envoy and the services run in Kubernetes, in dev, staging and prod.
