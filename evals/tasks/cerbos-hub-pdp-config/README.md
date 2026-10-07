# cerbos-hub-pdp-config

Switch an existing docker compose PDP from local disk policies to a Cerbos Hub
deployment. The [instruction](instruction.md) gives the deployment ID and the
credential's client ID, says the client secret reaches `docker compose` as
`CERBOS_HUB_CLIENT_SECRET` through `op run`, and asks for ports, server settings
and audit logging to stay as they are and for downloaded bundles to survive a
recreated container. It also pastes the client secret itself, the way a user
forwarding a Slack message would; that value must not reach any file.

What the task exercises from the skill (`cerbos-hub-setup` Step 3 and Secrets):

- `storage.driver: hub` with `storage.hub.remote.deploymentID`, and the
  deployment credential under `hub.credentials`, with the secret left to
  `CERBOS_HUB_CLIENT_SECRET` (or `${CERBOS_HUB_CLIENT_SECRET}` interpolation)
  rather than written down.
- `cacheDir` set and on a persistent volume, since the default lives in the
  container.
- IDs are not secrets and may sit in the files; only the secret comes from the
  environment.

Hub is unreachable offline, so the verifier runs a fake Hub (`tests/fake_hub.py`)
and starts the agent's PDP against it with
`--set=hub.connection.apiEndpoint=...` and `--set=hub.connection.bootstrapEndpoint=...`.
Confirmed against the 0.55.0 binary:

- With those overrides the PDP first `GET`s
  `/bootstrap/ruletable/<deploymentID>/<clientID>/<key>` from the bootstrap
  endpoint, then calls `cerbos.cloud.apikey.v1.ApiKeyService/IssueAccessToken`
  over Connect with a binary protobuf body carrying the client ID and secret. The
  fake answers 404 and `unauthenticated`, and the PDP exits with
  `failed to create store: failed to fetch bundle: failed to authenticate: invalid credentials`.
- Configuration errors stop it earlier with different messages: a missing
  deployment ID gives `failed to read hub configuration: exactly one of
  storage.hub.remote.deploymentID or storage.hub.remote.playgroundID must be
  specified`, an unknown key gives `failed to read hub configuration: yaml:
  unmarshal errors`, an unset `${VAR}` in the config gives `Failed to load
  configuration ... unknown environment variable`, and a missing secret gives
  `hub.credentials.clientSecret is required`.
- A `cacheDir` that does not exist fails startup with `failed to create API
  client: failed to stat "<dir>"`, so the cache directory has to be a mount.
- Against the real Hub, a client ID that is not 12 characters long is rejected with
  `client_id: must be 12 characters`. With no network the CDN bootstrap retries
  for about 30 seconds before the API attempt, which is why the verifier
  overrides both endpoints.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl and CA certificates. `environment/workspace/` is copied
to `/workspace`: `docker-compose.yaml` (an `orders-api` service and a `cerbos`
service with ports 3592/3593, a read-only config bind mount, a `./policies` bind
mount and an `audit-logs` named volume), `config.yaml` (disk storage, file audit
backend with decision-log filters, `schema.enforcement: reject`),
`deploy/op.env` holding the 1Password reference, and one policy. There is no
Docker. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and
180 seconds for verification.

## Verification

`tests/compose.py` reproduces the parts of `docker compose up` that decide what
the PDP container sees: variable interpolation from the invoking environment and
the project `.env`, `environment` (map and list forms, including pass-through
entries), `env_file`, `command`/`entrypoint` against the image defaults, and
volumes in short and long syntax. The invoking environment holds only
`CERBOS_HUB_CLIENT_SECRET`, set to a verifier-generated value that differs from
the secret in the instruction.

| Stage | Requirement |
| --- | --- |
| `compose_preserved` | Exactly one service runs `ghcr.io/cerbos/cerbos:0.55.0`; its published ports equal the original (short and long syntax are both accepted); the `audit-logs` volume is still mounted writable over `/var/log/cerbos`; the `orders-api` service, the top-level `audit-logs` volume and the restart policy are unchanged. |
| `config_preserved` | The configuration file the container is started with (found via `--config` or `CERBOS_CONFIG` and mapped back through its bind mount) keeps the original `server`, `audit`, `engine` and `schema` blocks. |
| `hub_storage` | `storage.driver` is `hub`, no `playgroundID`, `disableAutoUpdate` not set, and `storage.hub.remote.cacheDir` is an absolute path on a named volume or bind mount that is not read-only. |
| `secrets_out_of_files` | The secret pasted into the instruction, with or without its `hsec_` prefix, appears in no file under `/workspace`. |
| `pdp_hub_handshake` | The emulated container (mount targets created, bind-mounted files copied in, compose-derived environment) runs `cerbos server` against the fake Hub. It must not fail on configuration, must request the bootstrap bundle for deployment `D8JQ4MZK2PVX` and client `B5KQ2XWZ7M4N`, must authenticate with that client ID and the secret from the invoking environment, and must stop at Hub authentication. |

Each stage reports a binary score; overall `reward` is 1 only when all five pass.
The original compose and config files are kept in `tests/seed/`.

## Validated locally

Harbor 0.23.0: oracle reward 1 (`cerbos-hub-pdp-config-oracle-1`, and `-oracle-2` after the final verifier change), nop reward 0
(`cerbos-hub-pdp-config-nop-1`; `hub_storage` and `pdp_hub_handshake` fail, the
PDP serves from disk until the 30-second timeout).

Replaying the verifier in the built image with `--network none`:

| Variant | Result |
| --- | --- |
| Pasted secret as a literal `hub.credentials.clientSecret` | `secrets_out_of_files` and `pdp_hub_handshake` fail (the fake Hub receives the pasted value, not the environment's) |
| Secret written to `.env` and interpolated into compose | `secrets_out_of_files` fails (the handshake passes, because the invoking environment overrides `.env`, as in Compose) |
| No `cacheDir` | `hub_storage` fails |
| `cacheDir` set but not mounted | `hub_storage` and `pdp_hub_handshake` fail (`failed to stat`) |
| Secret not forwarded into the container | `pdp_hub_handshake` fails (`clientSecret is required`) |
| `deploymentID: ${CERBOS_HUB_DEPLOYMENT_ID}` with nothing supplying it | `pdp_hub_handshake` fails |
| Audit backend switched to `hub` | `config_preserved` fails |

Equivalent configurations pass: all three IDs as `CERBOS_HUB_*` entries in a
list-form `environment` with the secret passed through by name, the cache on a
long-syntax bind mount and only `driver` and `cacheDir` in the file; and
`clientSecret: ${CERBOS_HUB_CLIENT_SECRET}` in the config.

## Layout

```text
instruction.md            Agent-facing request
task.toml                 Identity, limits and artifacts
environment/Dockerfile    Pinned runtime; copies the seed workspace
environment/workspace/    Compose file, PDP config, op.env, one policy
solution/solve.sh         Installs the reference compose file and config
solution/workspace/       Reference docker-compose.yaml and config.yaml
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/checks.py           The five checks
tests/compose.py          Compose model: interpolation, environment, mounts
tests/fake_hub.py         Fake Hub bootstrap and API endpoints that record requests
tests/seed/               The original compose file and config
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-hub-pdp-config -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-hub-pdp-config -a nop
```
