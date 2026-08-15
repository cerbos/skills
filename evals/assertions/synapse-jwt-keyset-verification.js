/**
 * Deterministic check for the cerbos-synapse-extension `jwt-keyset-verification`
 * criterion.
 *
 * A declarative call/route mapper (or Envoy mapper) that extracts a JWT via
 * `auxData.jwt.token` but configures NO `keySetID` is accepting that token
 * UNVERIFIED — a security hole. Per Synapse's extension config schema
 * (server/pkg/extensions/conf.go, RequestAuxDataJWTConf): `Token` is the CEL
 * expression that extracts the raw JWT, and `KeySetID` is the CEL expression
 * selecting the keyset used to VERIFY it.
 *
 * Rule: in any YAML config that configures `auxData.jwt` with a non-empty
 * `token`, require a non-empty `keySetID` in the SAME jwt block.
 *
 * Neutral PASS when no `auxData.jwt` with a token is present anywhere, so cases
 * that don't use JWT auxData are never penalised (mirrors synapse-static.js).
 */
const fs = require('node:fs');
const path = require('node:path');
let yaml = null;
try { yaml = require('js-yaml'); } catch { yaml = null; }

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

// Recursively collect every `auxData.jwt` object in a parsed YAML document.
function findJwtBlocks(node, out) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) {
    for (const v of node) findJwtBlocks(v, out);
    return;
  }
  const aux = node.auxData;
  if (aux && typeof aux === 'object' && !Array.isArray(aux)) {
    const jwt = aux.jwt;
    if (jwt && typeof jwt === 'object' && !Array.isArray(jwt)) out.push(jwt);
  }
  for (const v of Object.values(node)) findJwtBlocks(v, out);
}

function nonEmpty(x) {
  return typeof x === 'string' ? x.trim().length > 0 : x != null && x !== false;
}

module.exports = (output, context) => {
  const dir = context && context.metadata && context.metadata.workingDir;
  if (!dir || !fs.existsSync(dir)) {
    return { pass: false, score: 0, reason: 'jwt-keyset-verification: no workingDir in metadata' };
  }

  const yamlFiles = walk(dir).filter((f) => /\.ya?ml$/.test(f));
  const blocks = []; // { file, jwt }

  for (const f of yamlFiles) {
    let text = '';
    try { text = fs.readFileSync(f, 'utf8'); } catch { continue; }
    if (!/auxData/.test(text) || !/jwt/.test(text)) continue;

    let found = [];
    if (yaml) {
      try {
        const docs = yaml.loadAll(text);
        for (const doc of docs) findJwtBlocks(doc, found);
      } catch {
        found = null; // fall through to text heuristic
      }
    }

    if (found && found.length > 0) {
      for (const jwt of found) blocks.push({ file: path.relative(dir, f), jwt });
    } else if (found === null || !yaml) {
      // Coarse text fallback: file mentions a jwt token but no keySetID at all.
      if (/token\s*:/.test(text)) {
        blocks.push({
          file: path.relative(dir, f),
          jwt: { token: 'unparsed', keySetID: /keySetID\s*:/.test(text) ? 'present' : undefined },
        });
      }
    }
  }

  const withToken = blocks.filter((b) => nonEmpty(b.jwt.token));
  if (withToken.length === 0) {
    return {
      pass: true,
      score: 1,
      reason: 'jwt-keyset-verification: no auxData.jwt token configured (N/A — deferred to judge)',
    };
  }

  const missing = withToken.filter((b) => !nonEmpty(b.jwt.keySetID)).map((b) => b.file);
  const pass = missing.length === 0;
  return {
    pass,
    score: pass ? 1 : 0,
    reason: pass
      ? `jwt-keyset-verification: every auxData.jwt token has a keySetID for verification (${withToken.length} block(s))`
      : `jwt-keyset-verification: auxData.jwt extracts a token with NO keySetID in ${missing.join(', ')} — JWT would be trusted unverified`,
  };
};
