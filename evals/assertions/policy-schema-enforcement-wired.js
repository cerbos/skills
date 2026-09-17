/**
 * Deterministic check for the cerbos-policy `schema-enforcement-wired` criterion.
 *
 * A JSON Schema under `_schemas/` only validates requests if a resource policy
 * points to it via a `schemas:` block (`principalSchema.ref`/`resourceSchema.ref`
 * using a `cerbos:///` URL). `cerbos compile` does NOT flag schema files that are
 * emitted but never referenced, so this closes that gap:
 *   - schemas-block:   if any `_schemas/**.json` exists, some resource policy must
 *                      declare a `schemas:` block (principalSchema/resourceSchema).
 *   - no-orphan-schemas: every emitted schema file must be referenced by a
 *                      `ref:`/`$ref` somewhere (path after `cerbos:///` matches the
 *                      file's location under `_schemas`).
 * Neutral PASS when no `_schemas` JSON files were emitted — schemas are optional,
 * so unrelated cases are never penalised (mirrors synapse-static.js).
 */
const fs = require('node:fs');
const path = require('node:path');

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (['.claude', '.git', 'node_modules'].includes(e.name)) continue;
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
    return { pass: false, score: 0, reason: 'schema-enforcement-wired: no workingDir in metadata' };
  }

  const files = walk(dir);
  const read = (f) => { try { return fs.readFileSync(f, 'utf8'); } catch { return ''; } };

  // Emitted schema files live under a `_schemas` directory (disk/git/blob stores).
  const schemaFiles = files.filter((f) => /(^|\/)_schemas\//.test(f) && /\.json$/i.test(f));
  if (schemaFiles.length === 0) {
    return {
      pass: true,
      score: 1,
      reason: 'schema-enforcement-wired: no _schemas emitted — schema validation is optional, nothing to wire (neutral pass)',
    };
  }

  const yamls = files.filter((f) => /\.ya?ml$/i.test(f));

  // Every schema file's cerbos ref path = the path after the `_schemas/` segment.
  const cerbosPathOf = (f) => f.replace(/^.*?(?:^|\/)_schemas\//, '');

  // Collect every ref target used anywhere (policy `ref:` + schema `$ref`),
  // normalised to the path after `cerbos:///`.
  const refTargets = new Set();
  const refRe = /cerbos:\/\/\/([^\s"'\\]+)/g;
  for (const f of [...yamls, ...schemaFiles]) {
    const text = read(f);
    let m;
    while ((m = refRe.exec(text)) !== null) refTargets.add(m[1]);
  }

  // A resource policy must actually declare a `schemas:` block for enforcement
  // to be possible at all.
  const policyYamls = yamls.filter((f) => !/_test\.ya?ml$/i.test(f));
  const hasSchemasBlock = policyYamls.some((f) => {
    const t = read(f);
    return /^\s*schemas:\s*$/m.test(t) && /(principalSchema|resourceSchema)\s*:/.test(t);
  });

  // Orphan schemas: emitted but never referenced by any ref/$ref.
  const orphans = schemaFiles
    .map((f) => ({ rel: path.relative(dir, f), target: cerbosPathOf(f) }))
    .filter((s) => !refTargets.has(s.target));

  const components = [
    {
      pass: hasSchemasBlock,
      score: hasSchemasBlock ? 1 : 0,
      reason: hasSchemasBlock
        ? 'schemas-block: a resource policy declares a schemas: block (principalSchema/resourceSchema)'
        : `schemas-block: ${schemaFiles.length} schema file(s) under _schemas/ but NO resource policy declares a schemas: block — schemas are decorative`,
    },
    {
      pass: orphans.length === 0,
      score: orphans.length === 0 ? 1 : 0,
      reason: orphans.length === 0
        ? 'no-orphan-schemas: every emitted schema is referenced by a ref/$ref'
        : `no-orphan-schemas: emitted but unreferenced: ${orphans.map((o) => `${o.rel} (expected ref cerbos:///${o.target})`).join(', ')}`,
    },
  ];

  const passed = components.filter((c) => c.pass).length;
  return {
    pass: components.every((c) => c.pass),
    score: passed / components.length,
    reason: `schema-enforcement-wired: ${passed}/${components.length} checks passed`,
    componentResults: components,
  };
};
