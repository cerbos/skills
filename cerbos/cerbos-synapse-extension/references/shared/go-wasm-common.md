# Go WASM Common Reference

Shared Go/extism-go-pdk patterns for Cerbos Synapse WASM extensions.

Requires `github.com/extism/go-pdk v1.1.3`. `tidwall/gjson` and `tidwall/sjson` for JSON manipulation; they keep binaries smaller than `encoding/json`.

## Build

```sh
go mod init example.com/myext
go get github.com/extism/go-pdk@v1.1.3 github.com/tidwall/gjson github.com/tidwall/sjson
GOOS=wasip1 GOARCH=wasm go build -buildmode=c-shared -o extensions/myext.wasm .
```

`-buildmode=c-shared` produces a reactor module that exports its symbols. Every module needs an empty `func main() {}`; the runtime never calls it. TinyGo builds roughly 10× smaller modules: `tinygo build -target wasip1 -buildmode=c-shared -o extensions/myext.wasm .`

## WASM Module Behaviors

- Modules are reactor (long-lived), pooled across parallel requests
- Each pool instance: independent memory; no shared state between instances
- Cross-instance state: cache host functions
- All exports return `0` success, non-zero failure
- Configuration via `pdk.GetConfig(key)`
- Every hook that produces output calls `pdk.Output`/`pdk.OutputJSON`, even to pass input through unchanged
- Logging: `pdk.Log(pdk.LogDebug, "msg")` (`LogTrace`, `LogDebug`, `LogInfo`, `LogWarn`, `LogError`) writes to the Synapse log tagged with the extension name; levels below `--log.level` are dropped
- Outbound HTTP (`pdk.NewHTTPRequest`) is blocked unless the extension's config entry lists the host in `allowedHosts`, next to `extensionURL`. Synapse ignores unknown keys, so a misspelled `allowedHosts` leaves requests blocked (HTTP 500) with no config error:

```yaml
extensions:
  routeExtensions:
    myRoute:
      extension:
        extensionURL: /extensions/myext.wasm
        allowedHosts: ["api.example.com"]
```

## Host Functions

Via `extism:host/user` module. Duration parameters in **milliseconds**.

Import: `//go:wasmimport extism:host/user <funcName>`.

| Function | Inputs | Output |
|----------|--------|--------|
| `cacheGet` | key ptr | value ptr |
| `cacheSet` | key ptr, value ptr, duration ms | status int |
| `cacheSetIfNotExists` | key ptr, value ptr, duration ms | status int |
| `cacheDelete` | key ptr | status int |
| `checkResources` | JSON request ptr | JSON response ptr |
| `planResources` | JSON request ptr | JSON response ptr |
| `dataSourceLookup` | JSON request ptr | JSON response ptr |

Return values report host errors only, not what happened:

- `cacheGet` returns offset `0` for a missing key. Test the offset; a stored value of any length, including 1 byte, is a hit.
- `cacheSetIfNotExists` returns `0` whether or not it wrote (an existing key is left unchanged), and `cacheDelete` returns `0` for a missing key. Read the key back when the outcome matters.
- `dataSourceLookup` for an unknown data source returns `{}` (no `result`) and logs `requested data source … does not exist` on the host.

## Import Declarations

Declare only the host functions the module uses:

```go
//go:wasmimport extism:host/user cacheGet
func _cacheGet(uint64) uint64

//go:wasmimport extism:host/user cacheSet
func _cacheSet(uint64, uint64, uint32) int32

//go:wasmimport extism:host/user cacheSetIfNotExists
func _cacheSetIfNotExists(uint64, uint64, uint32) int32

//go:wasmimport extism:host/user cacheDelete
func _cacheDelete(uint64) int32

//go:wasmimport extism:host/user checkResources
func _checkResources(uint64) uint64

//go:wasmimport extism:host/user planResources
func _planResources(uint64) uint64

//go:wasmimport extism:host/user dataSourceLookup
func _dataSourceLookup(uint64) uint64
```

## Helper Wrappers

Raw imports take Extism memory offsets. Standard wrappers (used by the per-kind examples):

```go
func cacheGetHelper(key string) ([]byte, bool) {
    keyMem := pdk.AllocateString(key)
    defer keyMem.Free()
    offset := _cacheGet(keyMem.Offset())
    if offset == 0 { // missing key
        return nil, false
    }
    mem := pdk.FindMemory(offset)
    return mem.ReadBytes(), true
}

func cacheSetHelper(key string, value []byte, durationMs uint32) {
    keyMem := pdk.AllocateString(key)
    defer keyMem.Free()
    valueMem := pdk.AllocateBytes(value)
    defer valueMem.Free()
    _cacheSet(keyMem.Offset(), valueMem.Offset(), durationMs)
}

func cacheSetIfNotExistsHelper(key string, value []byte, durationMs uint32) int32 {
    keyMem := pdk.AllocateString(key)
    defer keyMem.Free()
    valueMem := pdk.AllocateBytes(value)
    defer valueMem.Free()
    return _cacheSetIfNotExists(keyMem.Offset(), valueMem.Offset(), durationMs)
}

func cacheDeleteHelper(key string) int32 {
    keyMem := pdk.AllocateString(key)
    defer keyMem.Free()
    return _cacheDelete(keyMem.Offset())
}

// Decodes the lookup's result (any JSON value) into out. Returns false when the
// lookup fails or the result is missing or null.
func dataSourceLookupHelper(dataSource string, query any, out any) bool {
    reqJSON, err := json.Marshal(map[string]any{"dataSource": dataSource, "query": query})
    if err != nil {
        return false
    }
    reqMem := pdk.AllocateBytes(reqJSON)
    defer reqMem.Free()
    offset := _dataSourceLookup(reqMem.Offset())
    if offset == 0 {
        return false
    }
    var resp struct {
        Result json.RawMessage `json:"result"`
    }
    mem := pdk.FindMemory(offset)
    if err := json.Unmarshal(mem.ReadBytes(), &resp); err != nil ||
        len(resp.Result) == 0 || string(resp.Result) == "null" {
        return false
    }
    return json.Unmarshal(resp.Result, out) == nil
}

func outputJSON(v any) int32 {
    if err := pdk.OutputJSON(v); err != nil {
        pdk.SetError(err)
        return 1
    }
    return 0
}
```

## Manifest (optional)

Since 0.10, exporting `manifest` publishes metadata at `/_cerbos/meta` (JSON) and `/_cerbos/about` (HTML); `server.disableMeta: true` turns both off. Required fields: `apiVersion` (1), `name`, `version`; optional `owner`, `description`, `fieldMappings` (see the Synapse docs' manifest page).

```go
//go:wasmexport manifest
func manifest() int32 {
    return outputJSON(map[string]any{
        "apiVersion":  1,
        "name":        "user-enricher",
        "version":     "1.0.0",
        "owner":       "platform-team",
        "description": "Adds department and role to the principal",
    })
}
```
