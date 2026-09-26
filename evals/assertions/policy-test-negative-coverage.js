/**
 * Deterministic negative-coverage check for cerbos-policy test suites.
 *
 * `cerbos compile` runs bundled *_test.yaml suites, but a happy-path-only suite
 * (every expected outcome EFFECT_ALLOW) passes trivially and gives false
 * confidence that restrictions are enforced. The skill requires tests to
 * exercise restrictions, so we require at least one explicit EFFECT_DENY
 * expectation across the generated test suites. (The condition-boundary half of
 * the criterion is harder to verify structurally and is left to the judge.)
 *
 * PASS         = at least one *_test.{yaml,yml,json} asserts an EFFECT_DENY.
 * FAIL         = test suites exist but none assert any EFFECT_DENY (happy-path).
 * NEUTRAL PASS = no test suites at all (that gap is owned by the has-tests check
 *   in policy-static.js) or no workingDir — so this never fails a case it does
 *   not apply to (mirrors synapse-static.js).
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
    // Not applicable without a working dir — stay neutral, don't fail the case.
    return { pass: true, score: 1, reason: 'negative-coverage: no workingDir (not applicable)' };
  }

  const testFiles = walk(dir).filter((f) => /_test\.(ya?ml|json)$/.test(f));

  // No tests at all: the has-tests check in policy-static.js owns that gap.
  if (testFiles.length === 0) {
    return {
      pass: true,
      score: 1,
      reason: 'negative-coverage: no *_test files present (deferred to has-tests / judge)',
    };
  }

  const denying = testFiles
    .filter((f) => {
      try { return /EFFECT_DENY/.test(fs.readFileSync(f, 'utf8')); } catch { return false; }
    })
    .map((f) => path.relative(dir, f));

  const pass = denying.length > 0;
  return {
    pass,
    score: pass ? 1 : 0,
    reason: pass
      ? `negative-coverage: EFFECT_DENY asserted in ${denying.join(', ')}`
      : `negative-coverage: ${testFiles.length} test suite(s) present but none assert EFFECT_DENY — happy-path-only`,
  };
};
