# Policy CI for the billing repository

`/workspace` is our billing service's repository (a git checkout of `main`). The
Cerbos policies our PDPs run live in `policies/`, with their test suites and
fixtures. Our PDPs get those policies from a Cerbos Hub deployment, which builds
from the Hub policy store `billing-policies` (store ID `S7NQ4KDZ2WXM`). The store
is a plain upload store, not connected to GitHub, and today someone uploads to it
by hand from their laptop.

Add GitHub Actions CI for the policies:

- Every pull request into `main` must check the policies and fail if they would
  not build cleanly, so broken or failing policies cannot be merged. Last quarter
  a DENY rule passed its tests but silently did nothing when a request left out
  the attribute it checked; the PR check should catch that kind of condition
  too.
- Whatever lands on `main` must be uploaded to the `billing-policies` store
  automatically, so the store always matches `main`. Nothing else may write to
  the store: not pull requests and not other branches.

These repository secrets already exist; use whichever the job needs and never put
a credential value in the repository:

| Secret | What it is |
| --- | --- |
| `HUB_DEPLOY_CLIENT_ID`, `HUB_DEPLOY_CLIENT_SECRET` | Client credential from the Client credentials tab of our `billing-prod` Hub deployment (Read & write; our PDPs also use it to ship audit logs) |
| `HUB_POLICIES_CLIENT_ID`, `HUB_POLICIES_CLIENT_SECRET` | Client credential from the Client credentials tab of the `billing-policies` store (Read & write) |

Our workflows run on self-hosted runners (`runs-on: [self-hosted, linux]`) that
already have the `cerbos` and `cerbosctl` 0.55.0 binaries on `PATH`. They have
no Docker and cannot download tools at run time, so do not add install steps.
Keep the existing `app` workflow as it is.

Cerbos 0.55.0 and `cerbosctl` 0.55.0 are installed in this sandbox too. The
sandbox cannot reach Cerbos Hub or GitHub, so you cannot run an upload or a
workflow here.
