/**
 * Deterministic static checks for cerbos-synapse-extension outputs.
 * Synapse can't be RUN in CI (needs the licensed distribution image), so these
 * grep-level checks catch the specific, high-confidence failure modes the skill
 * itself calls out:
 *   - forbidden TS base64: btoa/atob instead of Host.arrayBufferToBase64()
 *   - wrong Envoy callback name: envoy_map_cerbos_response (correct: map_cerbos_response)
 *   - config wiring: a config.yaml references extensions.{proxy|route|dataSources}
 * Each is only asserted when relevant files are present, so cases that don't
 * touch a dimension aren't penalised.
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
    return { pass: false, score: 0, reason: 'synapse-static: no workingDir in metadata' };
  }

  const files = walk(dir);
  const read = (f) => {
    try { return fs.readFileSync(f, 'utf8'); } catch { return ''; }
  };
  const tsFiles = files.filter((f) => /\.(ts|js)$/.test(f) && !/\.d\.ts$/.test(f));
  const starFiles = files.filter((f) => /\.star$/.test(f));
  const configFiles = files.filter((f) => /config\.ya?ml$/.test(path.basename(f)));

  const components = [];

  // 1. Forbidden base64 in TS/WASM.
  const btoaHits = tsFiles.filter((f) => /\b(btoa|atob)\s*\(/.test(read(f))).map((f) => path.relative(dir, f));
  if (tsFiles.length > 0) {
    components.push({
      pass: btoaHits.length === 0,
      score: btoaHits.length === 0 ? 1 : 0,
      reason: btoaHits.length === 0
        ? 'no-forbidden-base64: no btoa/atob in TS (uses Host.arrayBufferToBase64 pattern)'
        : `no-forbidden-base64: btoa/atob found in ${btoaHits.join(', ')} — WASM has no btoa/atob`,
    });
  }

  // 2. Wrong Envoy callback name.
  const badEnvoy = [...starFiles, ...tsFiles].filter((f) => /envoy_map_cerbos_response/.test(read(f)))
    .map((f) => path.relative(dir, f));
  const mentionsEnvoy = [...starFiles, ...tsFiles].some((f) => /envoy/i.test(read(f)));
  if (mentionsEnvoy) {
    components.push({
      pass: badEnvoy.length === 0,
      score: badEnvoy.length === 0 ? 1 : 0,
      reason: badEnvoy.length === 0
        ? 'envoy-callback-name: no envoy_map_cerbos_response typo'
        : `envoy-callback-name: wrong callback name in ${badEnvoy.join(', ')} — correct is map_cerbos_response`,
    });
  }

  // 3. Config wiring present. All five extension kinds live under extensions.*:
  // proxy/route/dataSources, plus envoyExternalAuthz (Envoy) and envoyCheck.
  const WIRE_KEYS = /(proxyExtensions|routeExtensions|dataSources|envoyExternalAuthz|envoyCheck)/;
  if (configFiles.length > 0) {
    const wired = configFiles.some((f) => new RegExp(`extensions:\\s*[\\s\\S]*${WIRE_KEYS.source}`).test(read(f)));
    components.push({
      pass: wired,
      score: wired ? 1 : 0,
      reason: wired
        ? 'config-wired: config.yaml wires the extension under extensions.*'
        : 'config-wired: config.yaml present but no extensions.{proxyExtensions|routeExtensions|dataSources|envoyExternalAuthz} block',
    });
  }

  if (components.length === 0) {
    // Nothing statically checkable for this case — neutral pass, judge carries it.
    return { pass: true, score: 1, reason: 'synapse-static: no statically-checkable artifacts (deferred to judge)' };
  }

  const passed = components.filter((c) => c.pass).length;
  return {
    pass: components.every((c) => c.pass),
    score: passed / components.length,
    reason: `synapse-static: ${passed}/${components.length} static checks passed`,
    componentResults: components,
  };
};
