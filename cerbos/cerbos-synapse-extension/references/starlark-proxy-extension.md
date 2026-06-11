
# Cerbos Synapse Starlark Proxy Extension

`.star` scripts intercepting Cerbos `CheckResources` and `PlanResources` requests/responses passing through Cerbos Synapse. No compilation or specialized tooling.

Load with: `shared/starlark-environment.md` (host functions, modules, extension URL format, proto gotchas), `shared/patterns-and-gotchas.md` (run/test: `shared/run-and-test.md`).

## When to Use

- Simple principal enrichment or attribute injection
- Rapid prototyping of request/response modification
- Proxy logic without Go expertise
- Data source lookups with straightforward transformation

## When NOT to Use

- Complex enrichment requiring third-party libraries → use WASM proxy extension
- Performance-critical paths → use WASM proxy extension
- Static mapping → use CEL call mapper

## Exported Functions

Export at least one (Starlark names are snake_case):

| Export | Purpose |
|--------|---------|
| `augment_check_request` | Modify CheckResources request before PDP |
| `augment_check_response` | Modify CheckResources response before returning |
| `augment_plan_request` | Modify PlanResources request before PDP |
| `augment_plan_response` | Modify PlanResources response before returning |
| `augment_authzen_evaluation_request` | Modify AuthZEN AccessEvaluation request before PDP |
| `augment_authzen_evaluation_response` | Modify AuthZEN AccessEvaluation response before returning |
| `augment_authzen_evaluation_batch_request` | Modify AuthZEN AccessEvaluations (batch) request before PDP |
| `augment_authzen_evaluation_batch_response` | Modify AuthZEN AccessEvaluations (batch) response before returning |

Each receives the request/response as a struct, must return the (possibly modified) struct. AuthZEN variants: Synapse's AuthZEN-compatible endpoints. Check/Plan variants: standard Cerbos `CheckResources` / `PlanResources` flow.

## CheckResources Request Format

`augment_check_request` receives:

```python
struct(
    principal = struct(id = "...", roles = [...], attr = {...}),
    resources = [struct(
        resource = struct(kind = "...", id = "...", attr = {...}),
        actions = [...]
    )],
    aux_data = struct(jwt = struct(token = "...", key_set_id = "...")),
    request_id = "..."
)
```

## Implementation

Define only what you need — Cerbos Synapse skips undefined functions.

```python
def augment_check_request(req):
    attrs = {
        "alice": {"department": "engineering", "role": "admin"},
        "bob": {"department": "marketing", "role": "viewer"},
    }
    req.principal.attr = attrs.get(req.principal.id, {"department": "unknown", "role": "guest"})
    return req
```

Already-populated proto list/map fields: mutate in place, no rebuild needed. `roles` always populated for a valid principal, so appending is safe:

```python
def augment_check_request(req):
    req.principal.roles.append("auditor")
    return req
```

In-place writes to an **empty or absent** field (e.g. `principal.attr` not sent) are silently dropped — assign the whole field instead. See `shared/starlark-environment.md`.

### Enrichment from Data Source

```python
load("json", "json")

def augment_check_request(req):
    if req.principal.id != "":
        response = cerbos.data_source_lookup("userProfile", req.principal.id)
        if response != None and response.result != None:
            # Use JSON round-trip to safely extract data fields from proto struct
            # (dir() on proto structs includes builtin methods that can't be converted)
            result = json.decode(json.encode(response.result))
            # attr is usually empty here; in-place writes to an empty proto map
            # are not persisted, so build the map and assign it as a whole.
            attr = dict(req.principal.attr)
            for k in result:
                attr[k] = result[k]
            req.principal.attr = attr
    return req
```

Lookup returns a struct with a `result` field. The JSON round-trip safely extracts data fields — `dir()` on proto structs breaks; see `shared/starlark-environment.md`.

### With Caching

```python
load("json", "json")

def augment_check_request(req):
    cache_key = "principal:" + req.principal.id
    cached = cerbos.cache_get(cache_key)
    if cached != None:
        req.principal.attr = json.decode(cached)
        return req

    result = cerbos.data_source_lookup("userProfiles", req.principal.id)
    if result != None:
        req.principal.attr = result
        cerbos.cache_set(cache_key, json.encode(result), time.minute * 5)
    return req
```

## CheckResources Response Format

`augment_check_response` receives the CheckResources response. Each `results` entry: `resource` (`id`, `kind`, `policy_version`, `scope`) + `actions` proto map keyed by action name. Action values are `Effect` enums, read/written as strings (`"EFFECT_ALLOW"`, `"EFFECT_DENY"`, `"EFFECT_NO_MATCH"`):

```python
struct(
    request_id = "...",
    results = [struct(
        resource = struct(kind = "...", id = "...", policy_version = "...", scope = "..."),
        actions = {"view": "EFFECT_ALLOW", "delete": "EFFECT_DENY"}
    )]
)
```

### Modifying the Response

`actions` is a populated proto map (PDP returns an effect for every requested action) — overriding effects in place works, no rebuild needed. Test keys with `in` (proto maps have no `.get()`; see `shared/starlark-environment.md`):

```python
def augment_check_response(res):
    for result in res.results:
        # Force-deny a sensitive action regardless of the PDP decision
        if "delete" in result.actions:
            result.actions["delete"] = "EFFECT_DENY"
    return res
```

## Configuration

```yaml
extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  proxyExtensions:
    principalEnricher:
      extensionURL: /extensions/proxy.star
```
