# Loading the WASM module

`wasm` is the second required option on `new Embedded({ policies, wasm })`, and the only part of the setup that changes with the build tool. The published recipes are in [Loading the WebAssembly module](https://docs.cerbos.dev/cerbos-hub/deployments-epdp-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-embedded-pdp_hub-deployments-epdp-rules#_loading_the_webassembly_module).

The client accepts several shapes, which is why each bundler's idiomatic import works:

| Shape | Compiled with |
|---|---|
| `string` or `URL` | fetched, then `WebAssembly.instantiateStreaming` |
| `Response`, or a promise of one | `WebAssembly.instantiateStreaming` on the body |
| `ArrayBuffer`, `ArrayBufferView`, Node `Buffer`, or a promise of one | `WebAssembly.instantiate` |
| a precompiled `WebAssembly.Module` | used as-is |
| a function taking `WebAssembly.Imports` | called to instantiate — what Vite's `?init` import produces |

## Vite

```typescript
import wasm from "@cerbos/embedded-server/server.wasm?init";

const cerbos = new Embedded({ policies: { ruleId: "<RULE_ID>" }, wasm });
```

## Webpack

Configure `.wasm` files as assets, then import the URL:

```typescript
import wasmUrl from "@cerbos/embedded-server/server.wasm";

const cerbos = new Embedded({ policies: { ruleId: "<RULE_ID>" }, wasm: wasmUrl });
```

WebAssembly handling differs between Webpack versions; the Webpack documentation is the source for the config side.

## Rspack

```typescript
// rspack.config.ts
export default defineConfig({
  module: {
    rules: [{ test: /\.wasm$/, type: "asset/resource" }],
  },
});
```

Then import `wasmUrl` and pass it as `wasm`, exactly as with Webpack.

## Next.js (Turbopack)

Turbopack does not import `.wasm` directly. Copy the binary into `public/` and reference it by URL.

`scripts/copy-cerbos-wasm.mjs`:

```javascript
import { copyFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const source = fileURLToPath(
  import.meta.resolve("@cerbos/embedded-server/server.wasm"),
);
const destination = join(
  process.cwd(),
  "public",
  "wasm",
  "cerbos-epdp-server.wasm",
);

await mkdir(dirname(destination), { recursive: true });
await copyFile(source, destination);
```

Wire it to both hooks so a fresh clone and a build each get the binary:

```json
{
  "scripts": {
    "postinstall": "node scripts/copy-cerbos-wasm.mjs",
    "prebuild": "node scripts/copy-cerbos-wasm.mjs"
  }
}
```

```typescript
const cerbos = new Embedded({
  policies: { ruleId: "<RULE_ID>" },
  wasm: "/wasm/cerbos-epdp-server.wasm",
});
```

The copy is a build artefact: `.gitignore` it, since npm distributes the canonical file. It changes only when `@cerbos/embedded-server` is upgraded — not when policies change — so re-run the install after an upgrade to keep the copy matched to the installed package.

A Next.js application loading the ePDP this way is loading it for the browser. Its API routes, server actions and middleware still call a service PDP.

## Node.js

```typescript
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { Embedded } from "@cerbos/embedded-client";

const cerbos = new Embedded({
  policies: { ruleId: "<RULE_ID>" },
  wasm: readFile(
    fileURLToPath(import.meta.resolve("@cerbos/embedded-server/server.wasm")),
  ),
});
```

The promise is passed unawaited — the client awaits it.

## Edge runtimes

Two runtime restrictions bite here, both on Cloudflare Workers:

- No `WebAssembly.instantiateStreaming`, so a URL string is not a usable source. Supply the bytes or a precompiled `WebAssembly.Module` through whatever mechanism the platform gives for shipping a `.wasm` alongside the worker.
- No global timers at module scope, so `@cerbos/embedded-client` is imported **dynamically**, inside the handler:

```typescript
export default {
  async fetch(request) {
    const { Embedded } = await import("@cerbos/embedded-client");
    // ...
  },
} satisfies ExportedHandler;
```

Check the target runtime's own WebAssembly documentation before assuming a loading style carries across platforms.

## URL

```typescript
const cerbos = new Embedded({
  policies: { ruleId: "<RULE_ID>" },
  wasm: "https://cdn.example.com/cerbos-server.wasm",
});
```

## Precompiled module

```typescript
const cerbos = new Embedded({ policies: { ruleId: "<RULE_ID>" }, wasm: precompiledModule });
```
