# Move the orders PDP onto Cerbos Hub

`/workspace` holds the deployment for our orders service: `docker-compose.yaml`
runs the API next to a Cerbos PDP configured by `config.yaml`, and the PDP reads
policies from the local `./policies` directory. We now manage these policies in
Cerbos Hub and want the PDP to get its policies from there instead.

The platform team set up the Hub side and sent me this:

> Deployment `orders-prod`, deployment ID `D8JQ4MZK2PVX`.
> Client credential on that deployment (read only): client ID `B5KQ2XWZ7M4N`,
> client secret `hsec_q7T2vLx9Rk4mWzP8bN3cJf6YdA1sGh5E`.
> The secret is also in 1Password at `op://platform/cerbos-hub-orders-prod/secret`.

Production is started with
`op run --env-file=deploy/op.env -- docker compose up -d`, which puts the client
secret into the environment of the `docker compose` process as
`CERBOS_HUB_CLIENT_SECRET`. Nothing else comes from 1Password. The files in this
repository are committed and shared, so no secret may be written to any of them.

Update the compose file and the PDP configuration so the PDP fetches its policies
from that Hub deployment. Keep the PDP's ports, server settings and audit logging
exactly as they are, leave the `orders-api` service alone, and make sure a
restarted or recreated PDP container does not throw away what it has already
downloaded from Hub.

Cerbos 0.55.0 is installed in this sandbox as the native `cerbos` binary. Docker
is not available here, and the sandbox cannot reach Cerbos Hub, so you cannot
complete a real connection; a PDP started from your configuration would be
expected to fail only at the point of contacting Hub.
