/**
 * Deterministic check for the Envoy response-mode invariant.
 *
 * A Cerbos Synapse Starlark Envoy extension exports `envoy_check`, which returns
 * one of three modes (starlark-development.adoc "Envoy extension"; skill
 * reference references/starlark-envoy-extension.md "Return Modes"):
 *   - Direct response      -> struct(envoy_check_response = ...)
 *   - Cerbos mapping        -> struct(cerbos_mapping = ...)  (single-shot allow/deny)
 *   - Cerbos check request  -> struct(cerbos_check_request = ...) PLUS a second
 *                              function `map_cerbos_response` that builds the final
 *                              Envoy response from the Cerbos response.
 *
 * Doc invariant (starlark-development.adoc, "Cerbos check request"): "In this
 * mode, the extension must implement a second function named `map_cerbos_response`
 * to map the `CheckResources` response to an Envoy response." So whenever a
 * Starlark extension returns a `cerbos_check_request`, a correctly-named
 * `map_cerbos_response` function MUST be *defined*. This catches the structural
 * failure of choosing the dynamic-response mode but never implementing (or
 * misnaming) the required second callback.
 *
 * Scope: only Starlark Envoy extensions are checked. They export snake_case
 * `envoy_check` / `map_cerbos_response`; WASM Envoy extensions use camelCase
 * `envoyCheck` / `envoyMapCerbosResponse` (wasm-envoy-extension-{go,javascript}.md)
 * and are deliberately out of scope, so the `/envoy_check/` scoping regex (which
 * does not match `envoyCheck`) neutral-passes them. Every other case also returns
 * a neutral PASS so unrelated cases — and the cerbos_mapping / direct-response
 * modes, whose mode-fit is a semantic call left to the judge — are never
 * penalised (mirrors synapse-static.js).
 *
 * Detection uses a function-DEFINITION regex (`def\s+map_cerbos_response\s*\(`),
 * NOT a bare mention, so a callback named only inside a comment/string does not
 * count, and a misnamed `def envoy_map_cerbos_response(` correctly fails (the
 * `def ` is followed by `envoy_`, not `map_`).
 */
const fs = require('node:fs');
const path = require('node:path');

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (['.claude', '.git', 'node_modules', 'dist', 'build'].includes(e.name)) continue;
      walk(full, acc);
    } else {
      acc.push(full);
    }
  }
  return acc;
}

module.exports = (output, context) => {
  const dir = context && context.metadata && context.metadata.workingDir;
  if (!dir || !fs.existsSync(dir)) {
    return { pass: true, score: 1, reason: 'envoy-response-mode: no workingDir (deferred to judge)' };
  }

  const read = (f) => {
    try { return fs.readFileSync(f, 'utf8'); } catch { return ''; }
  };
  const codeFiles = walk(dir).filter((f) => /\.(star|ts|js)$/.test(f) && !/\.d\.ts$/.test(f));

  // Starlark Envoy extensions export snake_case `envoy_check`; only those files
  // are in scope (WASM camelCase envoyCheck is intentionally excluded).
  const envoyFiles = codeFiles.filter((f) => /envoy_check/.test(read(f)));
  if (envoyFiles.length === 0) {
    return { pass: true, score: 1, reason: 'envoy-response-mode: no Starlark Envoy extension present (N/A)' };
  }

  // Read the Envoy extension files together — the two entrypoints normally live
  // in one file, but join to be safe.
  const combined = envoyFiles.map(read).join('\n');

  // Mode (c) is selected when the extension returns a cerbos_check_request.
  if (!/cerbos_check_request/.test(combined)) {
    return {
      pass: true,
      score: 1,
      reason: 'envoy-response-mode: extension uses direct/cerbos_mapping mode (no cerbos_check_request) — second callback not required (mode-fit deferred to judge)',
    };
  }

  // A returned cerbos_check_request REQUIRES a `def map_cerbos_response(...)`.
  // Match a definition (not a bare mention in a comment/string); a misnamed
  // `def envoy_map_cerbos_response(` does not match (def is followed by envoy_).
  const hasCallback = /def\s+map_cerbos_response\s*\(/.test(combined);
  const rel = envoyFiles.map((f) => path.relative(dir, f)).join(', ');
  return {
    pass: hasCallback,
    score: hasCallback ? 1 : 0,
    reason: hasCallback
      ? `envoy-response-mode: cerbos_check_request mode with a correctly-named map_cerbos_response callback (${rel})`
      : `envoy-response-mode: cerbos_check_request returned but no correctly-named map_cerbos_response function defined in ${rel} — this mode requires the second callback`,
  };
};
