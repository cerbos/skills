# Python WASM Common Reference

Shared Python/extism-python-pdk patterns for Cerbos Synapse WASM extensions.

Requires `extism-py` CLI to compile Python to WASM. **Pure Python** dependencies only; native extension modules (.so/.dylib) do not work.

## WASM Module Behaviors

- Modules are reactor (long-lived), pooled across parallel requests
- Each pool instance has independent memory; no shared state between instances
- Use cache host functions for cross-instance state
- Configuration accessible via `extism.config_str(key)`

## Host Functions

Via `extism:host/user` module. Duration parameters in **milliseconds**.

Declare imports with `@extism.import_fn("extism:host/user", "funcName")`. All parameters annotated as `int` (raw memory offsets). Memory management: `extism.memory.alloc()`, `extism.memory.find()`, `extism.memory.free()`.

| Function | Inputs | Output |
|----------|--------|--------|
| `cacheGet` | key ptr | value ptr |
| `cacheSet` | key ptr, value ptr, duration ms | status int |
| `cacheSetIfNotExists` | key ptr, value ptr, duration ms | status int |
| `cacheDelete` | key ptr | status int |
| `checkResources` | JSON request ptr | JSON response ptr |
| `planResources` | JSON request ptr | JSON response ptr |
| `dataSourceLookup` | JSON request ptr | JSON response ptr |

### Import Declarations

Declare only the host functions your extension uses; `pdk-shim.wat` must list the same set.

```python
@extism.import_fn("extism:host/user", "cacheGet")
def _cache_get(key: int) -> int:
    pass

@extism.import_fn("extism:host/user", "cacheSet")
def _cache_set(key: int, value: int, ttl: int) -> int:
    pass

@extism.import_fn("extism:host/user", "cacheSetIfNotExists")
def _cache_set_if_not_exists(key: int, value: int, ttl: int) -> int:
    pass

@extism.import_fn("extism:host/user", "cacheDelete")
def _cache_delete(key: int) -> int:
    pass

@extism.import_fn("extism:host/user", "checkResources")
def _check_resources(req: int) -> int:
    pass

@extism.import_fn("extism:host/user", "planResources")
def _plan_resources(req: int) -> int:
    pass

@extism.import_fn("extism:host/user", "dataSourceLookup")
def _datasource_lookup(req: int) -> int:
    pass
```

## PDK Type Shim (i64/i32 Mismatch)

Python PDK compiles **all** import parameters as `i64`; host expects `i32` for TTL parameters and some return values. WAT shim (`pdk-shim.wat`) bridges the gap via `i32.wrap_i64` and `i64.extend_i32_s` conversions. Build pipeline:

1. `extism-py` compiles Python to `raw.wasm` (all-i64 imports)
2. `sed` renames `"extism:host/user"` imports to `"__pdk_shim__"`
3. `wasm-merge` combines with the shim module (which imports the real host functions with correct i32 signatures)

## Memory Helper Pattern

```python
def _alloc_string(s):
    return extism.memory.alloc(s.encode())

def _alloc_bytes(data):
    return extism.memory.alloc(data if isinstance(data, bytes) else data.encode())

def _read_bytes(offset):
    if not offset:
        return None
    handle = extism.memory.find(offset)
    if not handle or handle.length <= 1:
        return None
    return extism.memory.bytes(handle)
```

## Cache Helper Pattern

```python
def cache_get(key):
    key_handle = _alloc_string(key)
    result_offset = _cache_get(key_handle.offset)
    extism.memory.free(key_handle)
    return _read_bytes(result_offset)

def cache_set(key, value, expiry_ms):
    key_handle = _alloc_string(key)
    value_handle = _alloc_bytes(value)
    _cache_set(key_handle.offset, value_handle.offset, expiry_ms)
    extism.memory.free(key_handle)
    extism.memory.free(value_handle)

def cache_set_if_not_exists(key, value, expiry_ms):
    key_handle = _alloc_string(key)
    value_handle = _alloc_bytes(value)
    _cache_set_if_not_exists(key_handle.offset, value_handle.offset, expiry_ms)
    extism.memory.free(key_handle)
    extism.memory.free(value_handle)

def cache_delete(key):
    key_handle = _alloc_string(key)
    _cache_delete(key_handle.offset)
    extism.memory.free(key_handle)
```

## Build Pipeline

### pdk-shim.wat

Adapts host function signatures from all-i64 (Python PDK) to correct types. Include only host functions your extension uses.

```wat
(module
  (import "extism:host/user" "cacheGet" (func $real_cacheGet (param i64) (result i64)))
  (import "extism:host/user" "cacheSet" (func $real_cacheSet (param i64 i64 i32) (result i32)))
  (import "extism:host/user" "cacheSetIfNotExists" (func $real_cacheSetIfNotExists (param i64 i64 i32) (result i32)))
  (import "extism:host/user" "cacheDelete" (func $real_cacheDelete (param i64) (result i32)))
  (import "extism:host/user" "dataSourceLookup" (func $real_dataSourceLookup (param i64) (result i64)))
  (import "extism:host/user" "checkResources" (func $real_checkResources (param i64) (result i64)))
  (import "extism:host/user" "planResources" (func $real_planResources (param i64) (result i64)))

  (func (export "cacheGet") (param i64) (result i64)
    local.get 0
    call $real_cacheGet
  )
  (func (export "cacheSet") (param i64 i64 i64) (result i64)
    local.get 0
    local.get 1
    local.get 2
    i32.wrap_i64
    call $real_cacheSet
    i64.extend_i32_s
  )
  (func (export "cacheSetIfNotExists") (param i64 i64 i64) (result i64)
    local.get 0
    local.get 1
    local.get 2
    i32.wrap_i64
    call $real_cacheSetIfNotExists
    i64.extend_i32_s
  )
  (func (export "cacheDelete") (param i64) (result i64)
    local.get 0
    call $real_cacheDelete
    i64.extend_i32_s
  )
  (func (export "dataSourceLookup") (param i64) (result i64)
    local.get 0
    call $real_dataSourceLookup
  )
  (func (export "checkResources") (param i64) (result i64)
    local.get 0
    call $real_checkResources
  )
  (func (export "planResources") (param i64) (result i64)
    local.get 0
    call $real_planResources
  )
)
```

### Dockerfile.wasm-builder

Replace `SOURCE_FILE`, `WASM_FILENAME`, and `REQUIRED_EXPORTS` (grep pattern).

```dockerfile
FROM --platform=linux/amd64 ubuntu:24.04 AS tools
RUN apt-get update -qq && apt-get install -y -qq curl jq > /dev/null 2>&1
RUN ARCH=x86_64 \
    && WASM_TOOLS_URL=$(curl -sL https://api.github.com/repos/bytecodealliance/wasm-tools/releases/latest \
      | jq -r --arg arch "$ARCH" '.assets[] | select(.name | test($arch + "-linux.tar.gz$")) | .browser_download_url') \
    && curl -sL "$WASM_TOOLS_URL" | tar xz -C /usr/local/bin --strip-components=1 \
    && BINARYEN_URL=$(curl -sL https://api.github.com/repos/WebAssembly/binaryen/releases/latest \
      | jq -r --arg arch "$ARCH" '.assets[] | select(.name | test($arch + "-linux.tar.gz$")) | .browser_download_url') \
    && curl -sL "$BINARYEN_URL" | tar xz -C /usr/local --strip-components=1 \
    && EXTISM_PY_URL=$(curl -sL https://api.github.com/repos/extism/python-pdk/releases/latest \
      | jq -r --arg arch "$ARCH" '.assets[] | select(.name | test($arch + "-linux")) | select(.name | test("tar.gz$")) | .browser_download_url') \
    && curl -sL "$EXTISM_PY_URL" | tar xz --strip-components=1 -C /usr/local

FROM tools AS build
WORKDIR /build
COPY SOURCE_FILE .
RUN extism-py SOURCE_FILE -o raw.wasm

FROM tools AS merge
WORKDIR /merge
COPY --from=build /build/raw.wasm .
COPY pdk-shim.wat .
RUN wasm-tools parse pdk-shim.wat -o pdk-shim.wasm
RUN wasm-tools print raw.wasm \
    | sed 's/"extism:host\/user"/"__pdk_shim__"/g' \
    | wasm-tools parse -o raw-shimmed.wasm
RUN wasm-merge --enable-bulk-memory --enable-nontrapping-float-to-int \
    raw-shimmed.wasm main pdk-shim.wasm __pdk_shim__ \
    --rename-export-conflicts -o WASM_FILENAME

FROM tools AS verify
COPY --from=merge /merge/WASM_FILENAME /module.wasm
RUN wasm-tools print --skeleton /module.wasm | grep -E '^\s*\(export "(REQUIRED_EXPORTS)"' \
    || (echo "ERROR: missing required exports" && exit 1)

FROM scratch AS output
COPY --from=verify /module.wasm /WASM_FILENAME
```

### Makefile

```makefile
.PHONY: build clean

build:
	docker build --output type=local,dest=. -f Dockerfile.wasm-builder .

clean:
	rm -f *.wasm
```
