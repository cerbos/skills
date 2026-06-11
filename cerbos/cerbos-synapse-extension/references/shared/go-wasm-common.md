# Go WASM Common Reference

Shared Go/extism-go-pdk patterns for Cerbos Synapse WASM extensions.

Requires `github.com/extism/go-pdk v1.1.3`. `tidwall/gjson` and `tidwall/sjson` for JSON manipulation.

## WASM Module Behaviors

- Modules are reactor (long-lived), pooled across parallel requests
- Each pool instance: independent memory; no shared state between instances
- Cross-instance state: cache host functions
- All exports return `0` success, non-zero failure
- Configuration via `pdk.GetConfig(key)`

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
    mem := pdk.FindMemory(_cacheGet(keyMem.Offset()))
    result := mem.ReadBytes()
    if len(result) <= 1 {
        return nil, false
    }
    return result, true
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

func dataSourceLookupHelper(dataSource, query string) (map[string]any, bool) {
    reqJSON := fmt.Sprintf(`{"dataSource":"%s","query":"%s"}`, dataSource, query)
    reqMem := pdk.AllocateString(reqJSON)
    defer reqMem.Free()
    mem := pdk.FindMemory(_dataSourceLookup(reqMem.Offset()))
    result := mem.ReadBytes()
    if len(result) == 0 {
        return nil, false
    }
    var resp map[string]any
    if err := json.Unmarshal(result, &resp); err != nil {
        return nil, false
    }
    r, ok := resp["result"]
    if !ok || r == nil {
        return nil, false
    }
    m, ok := r.(map[string]any)
    return m, ok
}

func outputJSON(v any) int32 {
    if err := pdk.OutputJSON(v); err != nil {
        pdk.SetError(err)
        return 1
    }
    return 0
}
```
