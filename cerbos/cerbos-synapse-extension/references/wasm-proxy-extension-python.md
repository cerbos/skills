
# Cerbos Synapse WASM Proxy Extension (Python)

Python WASM modules intercepting Cerbos `CheckResources` and `PlanResources` requests/responses passing through Cerbos Synapse.

Load with: `shared/python-wasm-common.md` (module behaviors, host functions, memory/cache helpers, PDK shim, build pipeline), `shared/patterns-and-gotchas.md`. To run/test: `shared/run-and-test.md`.

## When to Use

- Principal enrichment using pure-Python libraries
- JSON-heavy attribute computation
- Rapid prototyping of proxy logic
- Response transformation when Go/TS are not preferred

## When NOT to Use

- Simple attribute injection -> use Starlark proxy extension
- Static request/response mapping -> use CEL call mapper
- Packages requiring native C extensions -> use WASM Go or TypeScript
## Exported Functions

Export at least one (WASM export names are camelCase):

| Export | Purpose |
|--------|---------|
| `augmentCheckRequest` | Modify CheckResources request before PDP |
| `augmentCheckResponse` | Modify CheckResources response before returning |
| `augmentPlanRequest` | Modify PlanResources request before PDP |
| `augmentPlanResponse` | Modify PlanResources response before returning |
| `augmentAuthzenEvaluationRequest` | Modify AuthZEN AccessEvaluation request before PDP |
| `augmentAuthzenEvaluationResponse` | Modify AuthZEN AccessEvaluation response before returning |
| `augmentAuthzenEvaluationBatchRequest` | Modify AuthZEN AccessEvaluations (batch) request before PDP |
| `augmentAuthzenEvaluationBatchResponse` | Modify AuthZEN AccessEvaluations (batch) response before returning |
| `cerbosInit` | Called once on module load; optional lifecycle hook |
| `cerbosDeinit` | Called once on module unload; optional lifecycle hook |

Each function: JSON input via `extism.input_str()`, JSON output via `extism.output_str()`.

## CheckResources Request Format

`augmentCheckRequest` receives the CheckResources request as JSON:

```json
{
  "principal": { "id": "...", "roles": ["..."], "attr": {} },
  "resources": [{ "resource": { "kind": "...", "id": "...", "attr": {} }, "actions": ["..."] }],
  "auxData": { "jwt": { "token": "...", "keySetID": "..." } },
  "requestID": "..."
}
```

## Implementation

Kind-specific logic only; host function import declarations (`cacheGet`, `cacheSet`, `cacheSetIfNotExists`, `cacheDelete`, `dataSourceLookup`), memory helpers, and cache helpers (`cache_get`, `cache_set`, `cache_set_if_not_exists`, `cache_delete`) are verbatim from `shared/python-wasm-common.md`.

```python
import json
import extism

# Import declarations + memory/cache helpers: shared/python-wasm-common.md

CACHE_TTL_MS = 300000

def _read_string(offset):
    if not offset:
        return ""
    handle = extism.memory.find(offset)
    if not handle:
        return ""
    return extism.memory.string(handle)

def datasource_lookup(req_json):
    req_handle = _alloc_string(req_json)
    result_offset = _datasource_lookup(req_handle.offset)
    extism.memory.free(req_handle)
    return _read_string(result_offset)

def enrich_principal(input_str):
    req = json.loads(input_str)
    principal = req.get("principal")
    if not principal or not isinstance(principal, dict):
        return input_str

    principal_id = principal.get("id", "")
    cache_key = "proxy:attrs:" + principal_id

    cached = cache_get(cache_key)
    if cached:
        attrs = json.loads(cached.decode())
        merge_attrs(principal, attrs)
        return json.dumps(req)

    attrs = lookup_from_datasource(principal_id)
    if attrs is None:
        attrs = get_hardcoded_attributes(principal_id)

    cache_set(cache_key, json.dumps(attrs), CACHE_TTL_MS)
    merge_attrs(principal, attrs)
    return json.dumps(req)

def lookup_from_datasource(principal_id):
    req_json = json.dumps({"dataSource": "userProfile", "query": principal_id})
    result_str = datasource_lookup(req_json)
    if not result_str:
        return None
    result = json.loads(result_str)
    result_val = result.get("result")
    if isinstance(result_val, dict):
        return result_val
    return None

def get_hardcoded_attributes(principal_id):
    if principal_id == "alice":
        return {"department": "engineering", "role": "admin"}
    if principal_id == "bob":
        return {"department": "marketing", "role": "viewer"}
    return {"department": "unknown", "role": "guest"}

def merge_attrs(principal, attrs):
    existing = principal.get("attr", {})
    if not isinstance(existing, dict):
        existing = {}
    existing.update(attrs)
    principal["attr"] = existing

@extism.plugin_fn
def cerbosInit():
    cache_set_if_not_exists("proxy:initialized", b"true", CACHE_TTL_MS)

@extism.plugin_fn
def cerbosDeinit():
    cache_delete("proxy:initialized")

@extism.plugin_fn
def augmentCheckRequest():
    extism.output_str(enrich_principal(extism.input_str()))

@extism.plugin_fn
def augmentCheckResponse():
    extism.output_str(extism.input_str())

@extism.plugin_fn
def augmentPlanRequest():
    extism.output_str(enrich_principal(extism.input_str()))

@extism.plugin_fn
def augmentPlanResponse():
    extism.output_str(extism.input_str())
```

## Configuration

```yaml
extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  dataSources:
    userProfile:
      extension:
        extensionURL: /extensions/datasource.star
  proxyExtensions:
    principalEnricher:
      extensionURL: /extensions/proxy.wasm
```
