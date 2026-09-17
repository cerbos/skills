/**
 * Deterministic structural checks for cerbos-policy outputs that the skill
 * mandates but the compiler does not enforce:
 *   - every policy/test YAML carries a `# yaml-language-server: $schema=` header
 *   - every rule block has a non-empty `name:` (audit-trail requirement)
 *   - at least one *_test.yaml exists (skill must ship tests)
 * Returns nested componentResults so each shows up individually in the report.
 */
const fs = require('node:fs');
const path = require('node:path');

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === '.claude' || e.name === '.git' || e.name === 'node_modules') continue;
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
    return { pass: false, score: 0, reason: 'policy-static: no workingDir in metadata' };
  }

  const yamls = walk(dir);
  const policyFiles = yamls.filter((f) => !/_test\.ya?ml$/.test(f));
  const testFiles = yamls.filter((f) => /_test\.ya?ml$/.test(f));

  // Don't let the header/name checks pass vacuously when nothing was generated.
  if (policyFiles.length === 0) {
    return { pass: false, score: 0, reason: 'policy-static: no policy YAML files were generated' };
  }

  const missingHeader = [];
  const missingRuleName = [];

  for (const f of yamls) {
    const text = fs.readFileSync(f, 'utf8');
    const rel = path.relative(dir, f);
    if (!/#\s*yaml-language-server:\s*\$schema=/.test(text.split('\n').slice(0, 3).join('\n'))) {
      missingHeader.push(rel);
    }
  }

  // Rule-name check: any `- actions:` / rule entry should have a sibling `name:`.
  for (const f of policyFiles) {
    const text = fs.readFileSync(f, 'utf8');
    const rel = path.relative(dir, f);
    // Heuristic: count rule blocks (lines with "- actions:") vs "name:" occurrences
    // inside a resourcePolicy `rules:` section. If there are rules but no names, flag.
    const ruleBlocks = (text.match(/^\s*-\s+actions:/gm) || []).length;
    const namedRules = (text.match(/^\s*name:/gm) || []).length;
    if (ruleBlocks > 0 && namedRules < ruleBlocks) {
      missingRuleName.push(`${rel} (${ruleBlocks} rules, ${namedRules} named)`);
    }
  }

  const components = [
    {
      pass: missingHeader.length === 0,
      score: missingHeader.length === 0 ? 1 : 0,
      reason: missingHeader.length === 0
        ? 'schema-header: all YAML files have $schema header'
        : `schema-header: missing on ${missingHeader.join(', ')}`,
    },
    {
      pass: missingRuleName.length === 0,
      score: missingRuleName.length === 0 ? 1 : 0,
      reason: missingRuleName.length === 0
        ? 'rule-names: every rule has a name'
        : `rule-names: unnamed rules in ${missingRuleName.join('; ')}`,
    },
    {
      pass: testFiles.length > 0,
      score: testFiles.length > 0 ? 1 : 0,
      reason: testFiles.length > 0
        ? `has-tests: ${testFiles.length} test suite(s) generated`
        : 'has-tests: no *_test.yaml generated',
    },
  ];

  const passed = components.filter((c) => c.pass).length;
  return {
    pass: components.every((c) => c.pass),
    score: passed / components.length,
    reason: `policy-static: ${passed}/${components.length} structural checks passed`,
    componentResults: components,
  };
};
