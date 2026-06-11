# Starlark Environment Reference

Common Starlark runtime environment for all Cerbos Synapse extensions.

## Host Functions

| Function | Description |
|----------|-------------|
| `cerbos.cache_get(key)` | Read from shared cache. Returns `None` if not found. |
| `cerbos.cache_set(key, value, expiry?, if_not_exists?)` | Write to shared cache. `expiry` uses `time.minute`, `time.hour`, etc. |
| `cerbos.cache_delete(key)` | Delete from cache. |
| `cerbos.check_resources(req)` | Call CheckResources on the PDP. |
| `cerbos.plan_resources(req)` | Call PlanResources on the PDP. |
| `cerbos.data_source_lookup(datasource, query, query_parameters?, cache_key?, cache_expiry?, cache_if_not_exists?)` | Query another configured data source. Cache options are flat kwargs (`cache_key`, `cache_expiry`, `cache_if_not_exists`). For ad-hoc caching outside a lookup, use `cerbos.cache_get` / `cerbos.cache_set` directly. |

## Context Variables

| Variable | Description |
|----------|-------------|
| `context.extension_name` | Name from config |
| `context.extension_kind` | Extension type: `"datasource"`, `"proxy"`, `"route"`, or `"envoy"` |
| `context.extension_config` | Configuration map from YAML `configuration` block |

## Built-ins

| Function | Description |
|----------|-------------|
| `struct(k=v, ...)` | Create struct objects, accessed with dot notation |
| `time.now()` | Current time |
| `time.parse_duration(d)` | Parse duration string |
| `time.parse_time(x, format?, location?)` | Parse a time string (defaults: RFC3339, UTC) |
| `time.from_timestamp(sec, nsec?)` | Unix time → Time object |
| `time.time(year?, month?, day?, hour?, minute?, second?, nanosecond?, location?)` | Construct a Time |
| `time.is_valid_timezone(loc)` | Check tz name validity |
| `time.minute`, `time.hour`, `time.second`, `time.millisecond`, `time.microsecond`, `time.nanosecond` | Duration constants |
| `math.floor(x)`, `math.ceil(x)`, `math.round(x)`, `math.fabs(x)`, `math.pow(x,y)`, `math.mod(x,y)`, `math.remainder(x,y)` | Math functions |

## Loadable Modules

Import with `load("module", "module")`:

| Module | Key Functions |
|--------|--------------|
| `json` | `decode`, `encode`, `dumps`, `indent`, `path`, `eval`, plus `try_decode` / `try_encode` / `try_dumps` / `try_path` / `try_eval` / `try_indent` (return `(value, err)` tuples) |
| `http` | `get`, `post`, `put`, `delete`, `patch`, `options`, `call`, `postForm`, `set_timeout`, `get_timeout` |
| `oauth` | `client_credentials_client(token_url, client_id, client_secret, scopes?, endpoint_params?, persist_key?)` — returns an HTTP client that attaches a token via OAuth client-credentials flow. Use `persist_key` to share the authenticated client across requests instead of re-authenticating per request. |
| `re` | `compile`, `match`, `search`, `findall`, `sub`, `split` |
| `base64` | `encode(src, encoding="standard")`, `decode(src, encoding="standard")` |
| `hashlib` | `md5`, `sha1`, `sha256`, `sha512` |
| `csv` | `read_all`, `write_all`, `write_dict` |
| `random` | `uuid`, `random`, `randint`, `randbytes`, `randb32`, `randstr`, `choice`, `choices`, `shuffle`, `uniform` |
| `stats` | `mean`, `median`, `mode`, `min`, `max`, `sum`, `variance`, `standard_deviation`, `percentile`, `correlation`, `pearson`, `geometric_mean`, `harmonic_mean`, `softmax`, `sigmoid`, `sample`, plus the `population_*`/`sample_*` variants — full descriptive-statistics module |
| `string` | `find`, `index`, `rfind`, `rindex`, `length`, `substring`, `codepoint`, `reverse`, `escape`/`unescape` (HTML), `quote`/`unquote` (shell) |

Most modules from [starlet](https://github.com/1set/starlet) — full per-function reference for `base64`, `csv`, `hashlib`, `http`, `json`, `random`, `re`, `stats`, `string` in each module's README at `https://github.com/1set/starlet/blob/master/lib/<module>/README.md`.

Also available via `load` in `*_test.star` suites run by `synapse test` — see `testing-framework.md`.

### OAuth persistence

`oauth.client_credentials_client` is request-scoped by default. Pass `persist_key` to share the authenticated client across requests — avoids re-authenticating with the upstream OAuth server every call. Runtime keys reuse on `persist_key` only, so make it unique per combination of OAuth parameters.

```python
load("oauth", "oauth")

def do_oauth_request():
    client = oauth.client_credentials_client(
        token_url=TOKEN_URL,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=[SCOPE],
        endpoint_params={"audience": "api.example.com"},
        persist_key="example-api",
    )
    resp = client.get(AUTHENTICATED_ENDPOINT)
    return resp.status_code
```

## REPL (debugging)

Synapse ships a Starlark REPL — test helper functions outside the request flow:

```sh
synapse starlark repl                    # interactive REPL
synapse starlark repl my_script.star     # load script's globals into the REPL
synapse starlark repl --exec my_script.star  # execute and exit
```

In REPL, `load("my_script.star", "my_script")` brings the script's exports into scope for direct calls. Ctrl+D exits.

## Extension URL Format

```yaml
extensionURL: /path/to/script.star
extensionURL: starlark+https://scripts.example.com/ext?checksum=sha256:...
```

File path must have `.star` extension. HTTP URLs must be prefixed with `starlark+`.

## Key Behaviors

- Fresh script instance per request; no shared global state between requests
- Cross-request state: `cerbos.cache_set`/`cerbos.cache_get`
- Structs: created with `struct(key=value)`, accessed with dot notation
- `context.extension_config`: the YAML `configuration` map

## Mutating proto lists and maps

Proto list and map fields (e.g. `principal.roles`, `principal.attr`, `resource.actions`) can be mutated **in place — but only when the field is already populated**:

```python
req.principal.roles.append("auditor")        # roles already has entries → persists
req.principal.attr["tier"] = "gold"           # attr already has entries → persists
result.actions["delete"] = "EFFECT_DENY"      # response actions map → persists
```

### Caveat: in-place writes to an empty or absent field are silently dropped

A proto list/map field with no entries — omitted from the request, or sent as `[]`/`{}` — is *unset*. Runtime hands the script a detached empty placeholder: `append()` and key assignment appear to succeed but are **not** reflected in the message the PDP evaluates (no error raised). Common case for enrichment, where `principal.attr` usually starts empty.

To populate an empty or absent field, assign the whole value:

```python
# attr may be empty — build the map and assign it as a whole
attr = dict(req.principal.attr)   # copy existing entries (empty dict if unset)
attr["department"] = "engineering"
req.principal.attr = attr

# or replace a list outright
req.resources[0].actions = ["view", "edit"]
```

In-place mutation works for already-populated fields; reassignment is safe when a field might be empty.

## Gotchas

### Proto maps don't support `.get()` or `hasattr()`

`req.query_params`, `req.headers`, `res.actions` are proto maps (`proto.map<K,V>`), not dicts. NO `.get()` or `hasattr()`. Use `in` operator and index access:

```python
# WRONG — crashes with "has no .get field or method"
user_param = req.query_params.get("user")

# WRONG — always returns False for proto map keys
if hasattr(res.actions, "GetRowFilter"):

# CORRECT
if "user" in req.query_params:
    user_id = req.query_params["user"].values[0]

if "GetRowFilter" in res.actions:
    effect = res.actions["GetRowFilter"]
```

### `cerbos.cache_set` only accepts string values

`value` must be string or bytes. Dict or struct → `got dict, want string`. Always JSON-encode before caching:

```python
# WRONG
cerbos.cache_set(key="k", value=my_dict, expiry=time.second * 30)

# CORRECT
cerbos.cache_set(key="k", value=json.encode(my_dict), expiry=time.second * 30)
cached = cerbos.cache_get(key="k")
if cached != None and cached != "":
    my_dict = json.decode(cached)
```

### `dir()` on proto structs includes builtin methods

`dir()` on a proto struct (e.g. `cerbos.data_source_lookup().result`) returns builtin methods like `clear` alongside data fields → `cannot convert *starlark.Builtin to google.protobuf.Value`. Use JSON round-trip to safely extract data:

```python
# WRONG — includes builtin methods
for k in dir(resp.result):
    attr[k] = getattr(resp.result, k)

# CORRECT
result = json.decode(json.encode(resp.result))
for k in result:
    attr[k] = result[k]
```

### `http.post` form data

Form-encoded POST: use `form_body={}` dict, not manual URL-encoding with a body string:

```python
# WRONG — may not send correct Content-Type or encoding
resp = http.post(url, body="grant_type=client_credentials&...", headers={"Content-Type": "application/x-www-form-urlencoded"})

# CORRECT
resp = http.post(url, form_body={"grant_type": "client_credentials", "client_id": "my-id"})
```
