/**
 * Deterministic cross-reference check for Cerbos derived roles wiring.
 *
 * A derived roles policy has NO effect unless the resource policy imports it via
 * `importDerivedRoles` (the entry must match the derived roles policy's top-level
 * `name`) AND a rule lists the derived role in its `derivedRoles` field. The
 * compiler catches a rule that references a derived role missing from imports,
 * but it does NOT flag a derived roles policy that is defined and never imported
 * (a dead/orphan policy). This check covers both:
 *   1. every derivedRole used in a resource rule is defined in a derived roles
 *      policy whose `name` is listed in that resource policy's importDerivedRoles
 *   2. no derived roles policy is defined-but-never-imported (orphan)
 *
 * Neutral PASS when the output uses no derived roles at all, so unrelated cases
 * are never penalised (mirrors synapse-static.js).
 */
const fs = require('node:fs');
const path = require('node:path');
let yaml;
try { yaml = require('js-yaml'); } catch { yaml = null; }

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (['.claude', '.git', 'node_modules'].includes(e.name)) continue;
      walk(full, acc);
    } else if (/\.ya?ml$/.test(e.name)) {
      acc.push(full);
    }
  }
  return acc;
}

module.exports = (output, context) => {
  const dir = context && context.metadata && context.metadata.workingDir;
  if (!dir || !fs.existsSync(dir)) {
    return { pass: false, score: 0, reason: 'derived-roles-imported: no workingDir in metadata' };
  }
  if (!yaml) {
    // Can't parse without a YAML lib — defer to the judge rather than fail.
    return { pass: true, score: 1, reason: 'derived-roles-imported: yaml parser unavailable (deferred to judge)' };
  }

  const derivedPolicies = {}; // topLevelName -> { file, defs:Set<string> }
  const resourcePolicies = []; // { file, imports:Set<string>, refs:Set<string> }

  for (const f of walk(dir)) {
    const rel = path.relative(dir, f);
    let docs;
    try {
      docs = yaml.loadAll(fs.readFileSync(f, 'utf8'));
    } catch {
      continue; // unparseable YAML is the compiler's problem, not ours
    }
    for (const doc of docs) {
      if (!doc || typeof doc !== 'object') continue;
      if (doc.derivedRoles && doc.derivedRoles.name) {
        const defs = new Set(
          (doc.derivedRoles.definitions || [])
            .map((d) => d && d.name)
            .filter(Boolean),
        );
        derivedPolicies[doc.derivedRoles.name] = { file: rel, defs };
      }
      if (doc.resourcePolicy && typeof doc.resourcePolicy === 'object') {
        const imports = new Set(doc.resourcePolicy.importDerivedRoles || []);
        const refs = new Set();
        for (const rule of doc.resourcePolicy.rules || []) {
          for (const r of (rule && rule.derivedRoles) || []) refs.add(r);
        }
        resourcePolicies.push({ file: rel, imports, refs });
      }
    }
  }

  const anyDerived = Object.keys(derivedPolicies).length > 0;
  const anyRefs = resourcePolicies.some((rp) => rp.refs.size > 0);
  if (!anyDerived && !anyRefs) {
    return { pass: true, score: 1, reason: 'derived-roles-imported: no derived roles used (N/A)' };
  }

  // 1. Every referenced derived role must be defined in an IMPORTED policy.
  const refViolations = [];
  for (const rp of resourcePolicies) {
    for (const roleName of rp.refs) {
      const ok = [...rp.imports].some(
        (imp) => derivedPolicies[imp] && derivedPolicies[imp].defs.has(roleName),
      );
      if (!ok) {
        const definedSomewhere = Object.values(derivedPolicies).some((dp) => dp.defs.has(roleName));
        refViolations.push(
          definedSomewhere
            ? `${rp.file}: rule uses derivedRole "${roleName}" but its derived roles policy is not in importDerivedRoles`
            : `${rp.file}: rule uses derivedRole "${roleName}" which no derived roles policy defines`,
        );
      }
    }
  }

  // 2. No derived roles policy defined-but-never-imported (orphan).
  const importedNames = new Set(resourcePolicies.flatMap((rp) => [...rp.imports]));
  const orphans = Object.entries(derivedPolicies)
    .filter(([name]) => !importedNames.has(name))
    .map(([name, dp]) => `${dp.file} (derivedRoles "${name}" imported by no resource policy)`);

  const components = [
    {
      pass: refViolations.length === 0,
      score: refViolations.length === 0 ? 1 : 0,
      reason: refViolations.length === 0
        ? 'referenced-imported: every derivedRole used in a rule is imported and defined'
        : `referenced-imported: ${refViolations.join('; ')}`,
    },
    {
      pass: orphans.length === 0,
      score: orphans.length === 0 ? 1 : 0,
      reason: orphans.length === 0
        ? 'no-orphan: every derived roles policy is imported by a resource policy'
        : `no-orphan: ${orphans.join('; ')}`,
    },
  ];

  const passed = components.filter((c) => c.pass).length;
  return {
    pass: components.every((c) => c.pass),
    score: passed / components.length,
    reason: `derived-roles-imported: ${passed}/${components.length} checks passed`,
    componentResults: components,
  };
};
