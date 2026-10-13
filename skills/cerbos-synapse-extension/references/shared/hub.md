# Synapse and Cerbos Hub

Local development reads policies from disk. In production the in-process PDP sources them from a Hub deployment as signed, pre-compiled bundles, and ships its audit trail back.

## Policy distribution

```yaml
pdp:
  inProcess:
    hub:
      credentials:
        clientID: "${CERBOS_HUB_CLIENT_ID}"
        clientSecret: "${CERBOS_HUB_CLIENT_SECRET}"
        pdpID: "synapse-1"          # optional; names this instance in Hub
    storage:
      driver: "hub"
      hub:
        remote:
          deploymentID: "YOUR_DEPLOYMENT_ID"
          cacheDir: /var/lib/synapse/hub-cache   # optional; must exist before start
```

**The gotcha that costs the most time: a `hub` section at the *root* of the Synapse config is ignored.** It has to sit under `pdp.inProcess`. The same applies to `storage` and `audit`. Configuration that looks right and does nothing is almost always this.

Set `playgroundID` instead of `deploymentID` to point at a playground; exactly one of the two may be set, and both set stops the PDP starting. `CERBOS_HUB_DEPLOYMENT_ID` and `CERBOS_HUB_PLAYGROUND_ID` override the configured value, with the deployment winning if both are present.

Credentials must belong to the deployment being fetched — a policy *store* credential cannot pull deployment bundles.

## Audit

```yaml
pdp:
  inProcess:
    audit:
      enabled: true
      backend: hub
      hub:
        storagePath: /var/lib/synapse/audit    # local buffer; use persistent storage
        mask:
          metadata: ["authorization"]
          checkResources: ["inputs[*].principal.attr.ssn"]
```

Audit upload needs **Read & write** deployment credentials; the same pair covers bundle download and audit upload.

What Hub receives is the request *as the PDP evaluated it* — after proxy extensions ran. An attribute an extension fetched from a directory or database appears in the decision entry and is searchable in the Hub console, which is the part a plain PDP audit trail cannot show. Every entry is annotated with:

| Key | Value |
|---|---|
| `cerbos.dev/synapse/version` | The running Synapse version |
| `cerbos.dev/synapse/extensions` | The proxy extensions that processed the request, in order |
| your own keys | From `audit.instanceAnnotations` at the *root* of the config — environment, region, cluster |

Mask paths naming a protobuf field use the lowerCamelCase JSON name, and a path that matches nothing is accepted silently rather than erroring — verify masks against real entries. Details: the `cerbos-audit-insights` skill.

## Gatewaying an existing PDP fleet

With `pdp.external`, Hub configuration belongs on the upstream PDP and Synapse needs no Hub credentials at all. Root-level `audit.instanceAnnotations` still applies, since Synapse adds those before forwarding.

Setting Hub up in the first place: the `cerbos-hub-setup` skill, or [Hub getting started](https://docs.cerbos.dev/cerbos-hub/getting-started?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-synapse-extension_hub-getting-started).
