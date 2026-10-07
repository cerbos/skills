
# Cerbos Synapse Starlark Data Source

`.star` scripts implementing custom data source lookups — attribute data for other Cerbos Synapse extensions. No compilation.

Load with: `shared/starlark-environment.md` (host functions, modules, extension URL format, proto gotchas), `shared/patterns-and-gotchas.md` (run/test: `shared/run-and-test.md`).

## When to Use

- Simple HTTP API lookups for user/resource attributes
- Data transformation from external services
- Rapid prototyping of data source behavior
- Data source logic without Go expertise

## When NOT to Use

- Database drivers requiring compiled libraries → use WASM data source
- High-throughput lookups needing compiled performance → use WASM data source
- SQL databases → use built-in sqldb data source

## Exported Functions

| Export | Purpose |
|--------|---------|
| `lookup` | Handle data source lookup request, return result |

## Lookup Request Object

`lookup` receives:

```python
struct(
    data_source = "myDataSource",
    query = "simon",
    query_parameters = {"employee_id": "simon"},   # optional
    cache_options = struct(                        # 0.10+, when the caller passes cache kwargs
        cache_key = "simon",
        cache_expiry = time.minute,
        if_not_exists = True,
    ),
)
```

`query` can be any type (string, struct, etc). `query_parameters` values can be any type; numbers arrive as `float`. `cache_options` is always present; `cache_key` is `""` unless the caller passed cache kwargs to `cerbos.data_source_lookup`.

If callers may pass different formats, check with `type()`:

```python
def lookup(req):
    if type(req.query) == "string":
        user_id = req.query
    else:
        user_id = req.query.userId
```

## Lookup Response

Return struct with `result` field:

```python
struct(result = {"department": "engineering", "role": "senior"})
```

`result` can be any type. Item not found → return `struct(result = None)`.

## Implementation

```python
def lookup(req):
    result = {"output": "hello from starlark lookup", "query": req.query}
    return struct(result = result)
```

### HTTP API Lookup

```python
load("http", "http")
load("json", "json")

def lookup(req):
    api_url = context.extension_config["apiEndpoint"]
    resp = http.get(api_url + "/users/" + req.query)
    user = json.decode(resp.body())
    return struct(result = {"department": user["department"], "role": user["role"]})
```

### With Caching

```python
load("http", "http")
load("json", "json")

def lookup(req):
    cache_key = "user:" + str(req.query)
    cached = cerbos.cache_get(cache_key)   # "" on a miss
    if cached:
        return struct(result = json.decode(cached))

    resp = http.get(context.extension_config["apiEndpoint"] + "/users/" + str(req.query))
    user = json.decode(resp.body())
    result = {"department": user["department"], "role": user["role"]}
    cerbos.cache_set(cache_key, json.encode(result), time.minute * 5)
    return struct(result = result)
```

### Honouring Caller Cache Options

Synapse passes the caller's `cache_key` / `cache_expiry` / `cache_if_not_exists` through in `req.cache_options` and does not cache custom data source results itself. Apply them in `lookup`; `cache_expiry` is a proto `Duration`, so convert it for `cerbos.cache_set`:

```python
load("json", "json")

def lookup(req):
    opts = req.cache_options
    if opts.cache_key:
        cached = cerbos.cache_get(opts.cache_key)   # "" on a miss
        if cached:
            return struct(result = json.decode(cached))

    result = fetch_user(req.query)   # your lookup logic

    if opts.cache_key:
        expiry = time.second * opts.cache_expiry.seconds if opts.cache_expiry.seconds else None
        cerbos.cache_set(opts.cache_key, json.encode(result), expiry, opts.if_not_exists)
    return struct(result = result)
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
```

With extension configuration:

```yaml
extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  dataSources:
    userProfile:
      extension:
        extensionURL: /extensions/datasource.star
        configuration:
          apiEndpoint: "https://api.example.com"
```

## Consuming a Data Source

Called from proxy extensions via `cerbos.data_source_lookup()`. Example enricher:

```python
load("json", "json")

def augment_check_request(req):
    if req.principal.id != "":
        response = cerbos.data_source_lookup("userProfile", req.principal.id)
        if response != None and response.result != None:
            result = json.decode(json.encode(response.result))
            for k in result:
                req.principal.attr[k] = result[k]
    return req
```

**Note**: Use the JSON round-trip to safely extract data fields — `dir()` on proto structs breaks; see `shared/starlark-environment.md`.

Wire both in config:

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
      extensionURL: /extensions/enricher.star
```
