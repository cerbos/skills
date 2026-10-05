# Sources

The guidance in this skill is checked against the `@cerbos/embedded-client` release named by `targetsEmbeddedClientVersion` in `SKILL.md`, and tracks the current Cerbos Hub documentation for ePDP rules. When moving to a new release, read the `@cerbos/embedded-client` and `@cerbos/embedded-server` release notes, update `targetsEmbeddedClientVersion` and the version stated in CLIENT.md, then recheck each page below against the section or reference file it backs — in particular the constructor options and defaults, the `Status` codes, the rule filter settings and limits, and the per-bundler loading recipes.

## Documentation

| Page | Backs |
|---|---|
| [Embedded PDPs](https://docs.cerbos.dev/cerbos-hub/deployments-epdp-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_hub-deployments-epdp-rules) | Setting one up in `SKILL.md`; RULES.md lifecycle, filtering, scopes, threat model, authentication and IP allowlist; WASM.md loading recipes |
| [Hub deployments](https://docs.cerbos.dev/cerbos-hub/deployments?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_hub-deployments) | ePDP rules living on a deployment in `SKILL.md` |
| [Hub getting started](https://docs.cerbos.dev/cerbos-hub/getting-started?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_hub-getting-started) | Policies reaching a Hub policy store first in `SKILL.md` |
| [Hub decision points](https://docs.cerbos.dev/cerbos-hub/decision-points?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_hub-decision-points) | The service PDP alternative in `SKILL.md`; CLIENT.md platform support |
| [Filtering resources](https://docs.cerbos.dev/cerbos/latest/recipes/filtering-resources?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_pdp-recipes-filtering-resources) | `planResources` for lists in Checking in `SKILL.md` |
| [Resource policies](https://docs.cerbos.dev/cerbos/latest/policies/resource_policies?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_pdp-policies-resource-policies) | RULES.md version filtering |
| [Scoped policies](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_pdp-policies-scoped-policies) | RULES.md scope filtering and ancestor inclusion |
| [Engine configuration](https://docs.cerbos.dev/cerbos/latest/configuration/engine?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_pdp-configuration-engine) | CLIENT.md `defaultPolicyVersion` |
| [Schema configuration](https://docs.cerbos.dev/cerbos/latest/configuration/schema?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_pdp-configuration-schema) | CLIENT.md `schemaEnforcement` |
| [Auxiliary data](https://docs.cerbos.dev/cerbos/latest/configuration/auxdata?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_pdp-configuration-auxdata) | CLIENT.md `decodeJWTPayload` |

## SDKs

- [`@cerbos/embedded-client` API reference](https://cerbos.github.io/cerbos-sdk-javascript/modules/_cerbos_embedded-client.html) and [`Options`](https://cerbos.github.io/cerbos-sdk-javascript/interfaces/_cerbos_embedded-client.Options.html): the Checking table in `SKILL.md`; CLIENT.md policy sources, bundle update options, engine options and errors; WASM.md accepted `wasm` shapes.
- `node_modules/@cerbos/embedded-server/lib/server.wasm` in the installed package: the engine size quoted in `SKILL.md`.
- [`@cerbos/grpc`](https://www.npmjs.com/package/@cerbos/grpc) and [`@cerbos/http`](https://www.npmjs.com/package/@cerbos/http): the service PDP clients named in `SKILL.md`.
