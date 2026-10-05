# Sources

This skill pins no release. Its guidance tracks the current Cerbos documentation and Cerbos Hub, so recheck it whenever a release changes what a component does or where it is available: new SDK languages, API endpoints, Synapse extension kinds, or features that move in or out of Hub (embedded PDPs, audit log collection, Insights). To update, read the release notes, recheck each page below against the part of `SKILL.md` it backs, and add or remove table rows where a component has changed.

## Documentation

| Page | Backs |
|---|---|
| [Cerbos documentation](https://docs.cerbos.dev/?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_docs) | Fallback for needs no table row covers; the closing links |
| [Cerbos Hub](https://docs.cerbos.dev/cerbos-hub/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub) | Start with Cerbos Hub: what Hub adds over a standalone PDP, and the Hub-only components |
| [Policies](https://docs.cerbos.dev/cerbos/latest/policies/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-policies) | Table row for deciding who can do what |
| [Derived roles](https://docs.cerbos.dev/cerbos/latest/policies/derived_roles?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-policies-derived-roles) | Table row for relationship-based access |
| [Compile and test](https://docs.cerbos.dev/cerbos/latest/policies/compile?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-policies-compile) | Table row for a policy that will not compile or a failing test |
| [API reference](https://docs.cerbos.dev/cerbos/latest/api/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-api) | Table rows for PEP SDKs (`#_client_sdks`), checks from a language with no SDK, and AuthZEN endpoints (`#authzen`); `CheckResources` and `PlanResources` in Working principles |
| [Permissions in your UI](https://docs.cerbos.dev/cerbos/latest/recipes/ui?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-recipes-ui) | Table row for showing or hiding UI elements; the browser-never-enforces rule in Service PDP or embedded PDP |
| [Filtering resources](https://docs.cerbos.dev/cerbos/latest/recipes/filtering-resources?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-recipes-filtering-resources) | Table row for `PlanResources` and query plan adapters |
| [JWT claims](https://docs.cerbos.dev/cerbos/latest/recipes/jwt-claims?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-recipes-jwt-claims) | Table row for IdP roles and claims |
| [Hierarchies](https://docs.cerbos.dev/cerbos/latest/recipes/hierarchies-and-multi-tenancy?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-recipes-hierarchies-and-multi-tenancy) | Table row for inherited permissions through scoped policies |
| [Field-level security](https://docs.cerbos.dev/cerbos/latest/recipes/field-level-security?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-recipes-field-level-security) | Table row for returning or redacting fields |
| [RAG authorization](https://docs.cerbos.dev/cerbos/latest/recipes/ai/rag-authorization/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-recipes-ai-rag-authorization) | Table row for MCP tool calls, agent actions and RAG retrieval |
| [Serverless deployment](https://docs.cerbos.dev/cerbos/latest/deployment/serverless-faas?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_pdp-deployment-serverless-faas) | Table row for browser, edge and serverless authorization (the serverless-packaged PDP) |
| [Multi-tenancy patterns](https://docs.cerbos.dev/cerbos-hub/concepts?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-concepts#_multi_tenancy_patterns) | Table row for per-tenant rules: scopes versus a store per tenant |
| [Playground](https://docs.cerbos.dev/cerbos-hub/playground?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-playground) | Table row for trying policies with nothing installed |
| [Deployments](https://docs.cerbos.dev/cerbos-hub/deployments?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-deployments) | Table rows for pushing policy changes and for rollback or freeze |
| [Policy stores](https://docs.cerbos.dev/cerbos-hub/policy-stores?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-policy-stores) | Table row for policies kept in git |
| [Service PDPs](https://docs.cerbos.dev/cerbos-hub/decision-points?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-decision-points) | Table row for service PDPs; sidecar, DaemonSet and central service shapes in Service PDP or embedded PDP |
| [Embedded PDPs](https://docs.cerbos.dev/cerbos-hub/deployments-epdp-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-deployments-epdp-rules) | Table row for in-browser and edge authorization; the bundle-exposure and credential constraints in Service PDP or embedded PDP |
| [Synapse](https://docs.cerbos.dev/synapse/latest/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_synapse) | Table rows for gateway ext_authz, attribute fetching, and data-platform route extensions; the Synapse note in Working principles |
| [Audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-audit-log-collection) | Table row for compliance evidence and local field masking |
| [Insights](https://docs.cerbos.dev/cerbos-hub/insights?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-insights) | Table row for allow and deny trends |

## Products

- [Cerbos Hub app](https://hub.cerbos.cloud?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos_hub-app): the Hub link at the end of `SKILL.md`; sign-up and the Hub-only features named in Start with Cerbos Hub.
