/**
 * Deterministic check for cerbos-synapse-extension: remote extension URLs must
 * be checksum-pinned.
 *
 * The Synapse docs strongly recommend pinning any extension loaded from a remote
 * source (HTTP(S), S3, GCS, or a starlark+http(s) script) to a specific version
 * with a `?checksum=sha256:...` parameter, for supply-chain security. Local file
 * paths (starting with `/`, a relative path) and `system://` built-ins are exempt
 * (the checksum is optional there).
 *
 * This walks the workspace, scans every YAML file for `extensionURL:` values,
 * and fails only if a REMOTE value is missing a `checksum=sha256:` pin. Cases
 * with no config / no remote extensionURL get a neutral PASS, so this never
 * penalises unrelated cases (mirrors synapse-static.js).
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

// A value is a REMOTE source if it is fetched over the network. Everything else
// (absolute/relative file paths, system:// built-ins) is a local source and the
// checksum is optional there.
const REMOTE_RE = /^(https?:\/\/|s3::|gcs::|starlark\+https?:\/\/)/i;
const URL_LINE_RE = /extensionURL:\s*(.+?)\s*$/;

function extractValue(rawLine) {
  const m = rawLine.match(URL_LINE_RE);
  if (!m) return null;
  let v = m[1].trim();
  // strip a trailing inline comment (# ...) that is not part of the URL
  v = v.replace(/\s+#.*$/, '').trim();
  // strip surrounding quotes
  if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
    v = v.slice(1, -1);
  }
  return v || null;
}

module.exports = (output, context) => {
  const dir = context && context.metadata && context.metadata.workingDir;
  if (!dir || !fs.existsSync(dir)) {
    return { pass: false, score: 0, reason: 'url-checksum: no workingDir in metadata' };
  }

  const yamlFiles = walk(dir).filter((f) => /\.ya?ml$/i.test(f));
  const remote = []; // { file, value, pinned }

  for (const f of yamlFiles) {
    let text = '';
    try { text = fs.readFileSync(f, 'utf8'); } catch { continue; }
    for (const line of text.split(/\r?\n/)) {
      const v = extractValue(line);
      if (!v) continue;
      if (!REMOTE_RE.test(v)) continue; // local / system:// — exempt
      remote.push({
        file: path.relative(dir, f),
        value: v,
        pinned: /checksum=sha256:/i.test(v),
      });
    }
  }

  if (remote.length === 0) {
    // No remote extensionURL to check — not applicable, neutral pass.
    return { pass: true, score: 1, reason: 'url-checksum: no remote extensionURL present (N/A)' };
  }

  const unpinned = remote.filter((r) => !r.pinned);
  const pass = unpinned.length === 0;
  return {
    pass,
    score: pass ? 1 : 0,
    reason: pass
      ? `url-checksum: all ${remote.length} remote extensionURL(s) pinned with checksum=sha256:`
      : `url-checksum: ${unpinned.length}/${remote.length} remote extensionURL(s) NOT checksum-pinned — ${unpinned.map((r) => `${r.file}: ${r.value}`).join('; ')}`,
  };
};
