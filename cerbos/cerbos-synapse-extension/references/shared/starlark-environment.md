# Starlark Environment Reference

Common Starlark runtime environment for all Cerbos Synapse extensions.

## Host Functions

| Function | Description |
|----------|-------------|
| `cerbos.cache_get(key)` | Read from shared cache. Returns `""` on a miss; guard with `if cached:` before decoding. |
| `cerbos.cache_set(key, value, expiry?, if_not_exists?)` | Write to shared cache. `expiry` uses `time.minute`, `time.hour`, etc. |
| `cerbos.cache_delete(key)` | Delete from cache. |
| `cerbos.check_resources(req)` | Call CheckResources on the PDP. |
| `cerbos.plan_resources(req)` | Call PlanResources on the PDP. |
| `cerbos.data_source_lookup(datasource, query, query_parameters?, cache_key?, cache_expiry?, cache_if_not_exists?)` | Query another configured data source. Cache options are flat kwargs (`cache_key`, `cache_expiry`, `cache_if_not_exists`); a custom data source only caches if its `lookup` applies them (`starlark-data-source.md`). For ad-hoc caching outside a lookup, use `cerbos.cache_get` / `cerbos.cache_set` directly. |

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
| `math.floor`, `ceil`, `round`, `fabs`, `pow`, `mod`, `remainder`, `sqrt`, `exp`, `log`, `hypot`, trig (`sin`, `cos`, `tan`, `atan2`, ...), `math.pi`, `math.e` | Math functions |

`time` and `math` are predeclared globals; `load()` them and the script fails with `unknown module`.

## Loadable Modules

Import with `load("module", "module")`:

| Module | Key Functions |
|--------|--------------|
| `json` | `decode`, `encode`, `encode_indent`, `dumps`, `indent`, `path`, `eval`, `validate`, `repair`, plus `try_*` variants (return `(value, err)` tuples) |
| `http` | `get`, `post`, `put`, `delete`, `patch`, `head`, `options`, `call`, `postForm`, `set_timeout`, `get_timeout`, plus `try_*` variants |
| `oauth` | `client_credentials_client(token_url, client_id, client_secret, scopes?, endpoint_params?, persist_key?)` — returns an HTTP client that attaches a token via OAuth client-credentials flow. Use `persist_key` to share the authenticated client across requests instead of re-authenticating per request. |
| `re` | `compile`, `match`, `search`, `findall`, `sub`, `split` |
| `base64` | `encode(src, encoding="standard")`, `decode(src, encoding="standard")` |
| `hashlib` | `md5`, `sha1`, `sha256`, `sha512` |
| `csv` | `read_all`, `read_dict`, `write_all`, `write_dict`, plus `try_*` variants |
| `random` | `uuid`, `random`, `randint`, `randbytes`, `randb32`, `randstr`, `choice`, `choices`, `shuffle`, `uniform` |
| `stats` | `mean`, `median`, `mode`, `min`, `max`, `sum`, `variance`, `standard_deviation`, `percentile`, `correlation`, `pearson`, `geometric_mean`, `harmonic_mean`, `softmax`, `sigmoid`, `sample`, plus the `population_*`/`sample_*` variants — full descriptive-statistics module |
| `string` | `find`, `index`, `rfind`, `rindex`, `length`, `substring`, `codepoint`, `reverse`, `head`/`tail`/`head_lines`/`tail_lines`, `truncate`, `escape`/`unescape` (HTML), `quote`/`unquote` (shell), constants (`ascii_letters`, `digits`, `whitespace`, ...) |

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
- Numbers inside `google.protobuf.Value` fields (`attr` values, lookup results, `query_parameters`, policy outputs) read as `float`: `1` arrives as `1.0`. Wrap with `int()` where an integer is needed.
- Declared proto fields always exist, so `hasattr(req, "principal")` is always true. Test a value such as `req.principal.id != ""` to see whether the caller sent it.

## Manifest (all kinds)

Every extension kind can export an optional `manifest()` describing itself. Synapse serves the manifests of active extensions at `/_cerbos/meta` (JSON) and `/_cerbos/about` (HTML); `server.disableMeta: true` turns both off. Recommended for any extension that ships beyond a prototype:

```python
def manifest():
    return struct(
        api_version = 1,                 # required, always 1
        name = "principal-enricher",     # required
        version = "1.0.0",               # required
        owner = "platform-team",
        description = "Adds HR attributes to principal.attr.employee",
    )
```

Optional `field_mappings` documents which request/response fields the extension changes (`targets`, `operation`, `value`); the full format is in the Synapse docs' extension manifest page.

## Mutating proto lists and maps

Mutate proto list and map fields (`principal.roles`, `principal.attr`, `resource.attr`, response `actions`) in place. Writes persist whether the field was populated, sent empty, or omitted:

```python
req.principal.roles.append("auditor")
req.principal.attr["tier"] = "gold"
req.resources[0].resource.attr["region"] = "eu"
result.actions["delete"] = "EFFECT_DENY"
```

Enrich by assigning individual keys. Assigning a new map (`req.principal.attr = {...}`) replaces every attribute the caller sent.

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

Removing a key: proto maps have no `.pop()`, and Starlark has no `del`. Rebuild the map without it; the comprehension keeps every other attribute:

```python
if "department" in req.principal.attr:
    req.principal.attr = {k: req.principal.attr[k] for k in req.principal.attr if k != "department"}
```

### `cerbos.cache_set` only accepts string values

`value` must be string or bytes. Dict or struct → `got dict, want string`. Always JSON-encode before caching:

```python
# WRONG
cerbos.cache_set(key="k", value=my_dict, expiry=time.second * 30)

# CORRECT
cerbos.cache_set(key="k", value=json.encode(my_dict), expiry=time.second * 30)
cached = cerbos.cache_get(key="k")
if cached:                      # a miss returns ""
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
