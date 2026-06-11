# TypeScript WASM Common Reference

Shared TypeScript/extism-js-pdk patterns for Cerbos Synapse WASM extensions.

Dependencies: `@extism/js-pdk`, `esbuild`, `typescript`. Build: esbuild (CJS, ES2020, bundled) then `extism-js` CLI.

## d.ts Rules

**Violating these crashes the WASM module:**
1. Export names MUST be **camelCase** (`cerbosInit`, not `cerbos_init`)
2. **Every declared export MUST have an implementation** in index.ts — extism-js generates broken stubs for unimplemented exports that crash with `unreachable`
3. Always include `/// <reference types="@extism/js-pdk" />` at the top

## Runtime Limitations

**No `btoa`/`atob`** in extism-js runtime. Use `Host.arrayBufferToBase64()` and `Host.base64ToArrayBuffer()` with `TextEncoder`/`TextDecoder`:

```ts
function encodeBase64(str: string): string {
  const bytes = new TextEncoder().encode(str);
  const buf = new ArrayBuffer(bytes.length);
  new Uint8Array(buf).set(bytes);
  return Host.arrayBufferToBase64(buf);
}

function decodeBase64(b64: string): string {
  return new TextDecoder().decode(Host.base64ToArrayBuffer(b64));
}
```

## WASM Module Behaviors

- Modules are reactor (long-lived), pooled across parallel requests
- Each pool instance has independent memory; no shared state between instances
- Use cache host functions for cross-instance state
- All exported functions return `0` for success, non-zero for failure
- Configuration accessible via `Config.get(key)`

## Host Functions

Via `extism:host/user` module. Duration parameters in **milliseconds**.

| Function | Inputs | Output |
|----------|--------|--------|
| `cacheGet` | key ptr | value ptr |
| `cacheSet` | key ptr, value ptr, duration ms | status int |
| `cacheSetIfNotExists` | key ptr, value ptr, duration ms | status int |
| `cacheDelete` | key ptr | status int |
| `checkResources` | JSON request ptr | JSON response ptr |
| `planResources` | JSON request ptr | JSON response ptr |
| `dataSourceLookup` | JSON request ptr | JSON response ptr |

## Host Function Declarations (src/index.d.ts)

Append to the kind-specific `declare module "main"` block. Declare only the host functions your module calls:

```ts
declare module "extism:host" {
  interface user {
    checkResources(reqPtr: PTR): PTR;
    planResources(reqPtr: PTR): PTR;
    cacheGet(keyPtr: PTR): PTR;
    cacheSet(keyPtr: PTR, valuePtr: PTR, ttlMs: I32): I32;
    cacheSetIfNotExists(keyPtr: PTR, valuePtr: PTR, ttlMs: I32): I32;
    cacheDelete(keyPtr: PTR): I32;
    dataSourceLookup(reqPtr: PTR): PTR;
  }
}
```

## Host Function Wrappers (src/index.ts)

Standard helpers wrapping `Host.getFunctions()` and `Memory`. Copy the ones your module uses:

```ts
function cacheGet(key: string): string | null {
  const { cacheGet: _cacheGet } = Host.getFunctions() as Record<string, Function>;
  const keyMem = Memory.fromString(key);
  const resultPtr = _cacheGet(keyMem.offset) as unknown as PTR;
  if (!resultPtr) return null;
  const resultMem = Memory.find(resultPtr);
  if (!resultMem || resultMem.len <= 1) return null;
  return resultMem.readString();
}

function cacheSet(key: string, value: string, ttlMs: number): number {
  const { cacheSet: _cacheSet } = Host.getFunctions() as Record<string, Function>;
  const keyMem = Memory.fromString(key);
  const valueMem = Memory.fromString(value);
  return _cacheSet(keyMem.offset, valueMem.offset, ttlMs) as unknown as number;
}

function cacheSetIfNotExists(key: string, value: string, ttlMs: number): number {
  const { cacheSetIfNotExists: _cacheSetIfNotExists } = Host.getFunctions() as Record<string, Function>;
  const keyMem = Memory.fromString(key);
  const valueMem = Memory.fromString(value);
  return _cacheSetIfNotExists(keyMem.offset, valueMem.offset, ttlMs) as unknown as number;
}

function cacheDelete(key: string): number {
  const { cacheDelete: _cacheDelete } = Host.getFunctions() as Record<string, Function>;
  const keyMem = Memory.fromString(key);
  return _cacheDelete(keyMem.offset) as unknown as number;
}

// JSON-in/JSON-out host calls. Inputs and outputs are JSON strings.
// dataSourceLookup input: {"dataSource": "...", "query": <any JSON>}; output: {"result": <any JSON>}
function checkResources(reqJSON: string): string {
  const { checkResources: _checkResources } = Host.getFunctions() as Record<string, Function>;
  const reqMem = Memory.fromString(reqJSON);
  const resultPtr = _checkResources(reqMem.offset) as unknown as PTR;
  const resultMem = Memory.find(resultPtr);
  if (!resultMem) return "{}";
  return resultMem.readString();
}

function planResources(reqJSON: string): string {
  const { planResources: _planResources } = Host.getFunctions() as Record<string, Function>;
  const reqMem = Memory.fromString(reqJSON);
  const resultPtr = _planResources(reqMem.offset) as unknown as PTR;
  const resultMem = Memory.find(resultPtr);
  if (!resultMem) return "{}";
  return resultMem.readString();
}

function dataSourceLookup(reqJSON: string): string {
  const { dataSourceLookup: _dataSourceLookup } = Host.getFunctions() as Record<string, Function>;
  const reqMem = Memory.fromString(reqJSON);
  const resultPtr = _dataSourceLookup(reqMem.offset) as unknown as PTR;
  const resultMem = Memory.find(resultPtr);
  if (!resultMem) return "{}";
  return resultMem.readString();
}
```
