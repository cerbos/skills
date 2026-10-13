# Invoice service

A small HTTP service that lets employees view their invoices and lets managers
approve submitted invoices in the cost centres they manage. Every request is
authorized by the Cerbos PDP.

## Running locally

```sh
cerbos server --config /workspace/cerbos/config.yaml &   # PDP on :3592 / :3593
python /workspace/app/app.py                              # service on :8000
```

Environment variables (all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8000` | Listen port |
| `CERBOS_URL` | `http://localhost:3592` | PDP HTTP address |
| `INVOICES_FILE` | `app/data/invoices.json` | Invoice data |
| `APP_JWT_SECRET` | `dev-only-invoice-secret` | HS256 secret shared with the identity gateway |

## API

| Request | Result |
| --- | --- |
| `GET /invoices/<id>` | The invoice as JSON, or 403 |
| `POST /invoices/<id>/approve` | The approved invoice as JSON, or 403 |

The web UI consumes the JSON shape returned by these endpoints.

## Identity tokens

The identity gateway issues HS256 tokens with `aud: invoices` and these claims:

| Claim | Example |
| --- | --- |
| `sub` | `maria.garcia` |
| `roles` | `["manager"]` |
| `department` | `"Engineering"` |
| `managed_cost_centers` | `["CC-100", "CC-200"]` (managers only) |
| `approval_limit` | `5000` (managers only) |

Mint a development token with PyJWT:

```sh
python -c 'import jwt; print(jwt.encode({"sub": "maria.garcia", "aud": "invoices", "roles": ["manager"], "department": "Engineering", "managed_cost_centers": ["CC-100", "CC-200"], "approval_limit": 5000}, "dev-only-invoice-secret", algorithm="HS256"))'
```
