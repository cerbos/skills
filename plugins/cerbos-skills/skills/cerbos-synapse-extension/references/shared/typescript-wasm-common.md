# TypeScript WASM Common Reference

Shared TypeScript/extism-js-pdk patterns for Cerbos Synapse WASM extensions.

Dependencies: `@extism/js-pdk`, `esbuild`, `typescript`, plus the `extism-js` CLI from the extism/js-pdk releases page (`extism-js --version`).

## Build

```sh
npm init -y
npm install --save-dev @extism/js-pdk esbuild typescript
npm pkg set type=commonjs
npm pkg set scripts.build="node esbuild.js && extism-js dist/index.js -i src/index.d.ts -o extensions/myext.wasm"
```

The PDK needs CommonJS output. `esbuild.js`:

```js
require('esbuild').build({
  entryPoints: ['src/index.ts'],
  outdir: 'dist',
  bundle: true,
  format: 'cjs',
  target: ['es2020'],
});
```

`tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "es2020",
    "module": "commonjs",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"]
}
```

Build with `npm run build`. esbuild strips types without checking them; run `npx tsc --noEmit` to typecheck.

### PDK types in `index.ts`

Start `src/index.ts` with a path reference to the PDK's declarations, so `tsc` knows `Host`, `Memory` and `Config`:

```ts
/// <reference path="../node_modules/@extism/js-pdk/dist/index.d.ts" />
```

Two traps make the obvious alternatives fail with `Cannot find name 'Host'`: `tsc` ignores `src/index.d.ts` because it sits next to `src/index.ts` (it looks like that file's build output), and `@extism/js-pdk` 1.1.1's `exports` map resolves `/// <reference types="@extism/js-pdk" />` to nothing from a `.ts` file. `skipLibCheck` silences the PDK declarations' own unresolved `core-js` imports. Leave `Host` to the PDK rather than redeclaring it.

## d.ts Rules

**Violating these crashes the WASM module:**
1. Export names MUST be **camelCase** (`cerbosInit`, not `cerbos_init`)
2. **Every declared export MUST have an implementation** in index.ts — extism-js generates broken stubs for unimplemented exports that crash with `unreachable`
3. Always include `/// <reference types="@extism/js-pdk" />` at the top (extism-js reads this file; `tsc` does not, see above)

## Runtime Limitations

`extism-js` before 1.6 has no `btoa`/`atob` (1.6 added them, with `fetch`, `Buffer` and `crypto`). This encoding works on every version, so prefer it unless you pin `extism-js` 1.6+:

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
- Logging: `console.debug("msg")` (also `trace`, `log`/`info`, `warn`, `error`) writes to the Synapse log tagged with the extension name; levels below `--log.level` are dropped
- Outbound HTTP (`Http.request`) is blocked unless the extension's config entry lists the host in `allowedHosts`, next to `extensionURL`. Synapse ignores unknown keys, so a misspelled `allowedHosts` leaves requests blocked (HTTP 500) with no config error:

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

- `cacheGet` returns pointer `0` for a missing key. Test the pointer; a stored value of any length, including 1 byte, is a hit.
- `cacheSetIfNotExists` returns `0` whether or not it wrote (an existing key is left unchanged), and `cacheDelete` returns `0` for a missing key. Read the key back when the outcome matters.
- `dataSourceLookup` for an unknown data source returns `{}` (no `result`) and logs `requested data source … does not exist` on the host.

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
  if (!resultPtr) return null; // missing key
  return Memory.find(resultPtr).readString();
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

## Manifest (optional)

Since 0.10, exporting `manifest` publishes metadata at `/_cerbos/meta` (JSON) and `/_cerbos/about` (HTML); `server.disableMeta: true` turns both off. Required fields: `apiVersion` (1), `name`, `version`; optional `owner`, `description`, `fieldMappings` (see the Synapse docs' manifest page). Declare `export function manifest(): void;` in `src/index.d.ts`, then:

```ts
export function manifest() {
  Host.outputString(JSON.stringify({
    apiVersion: 1,
    name: "user-enricher",
    version: "1.0.0",
    owner: "platform-team",
    description: "Adds department and role to the principal",
  }));
}
```
