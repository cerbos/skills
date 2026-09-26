/**
 * Deterministic guard for the `role-policy-cannot-grant` criterion.
 *
 * Cerbos role policies are an ADDITIVE CONSTRAINT: their `allowActions` list can
 * only NARROW access. An action is permitted only when BOTH a role policy AND a
 * matching resource policy allow it — a role policy can never grant on its own,
 * 'which is why a resource policy is always required' (docs: policies/evaluation
 * and policies/role_policies).
 *
 * This check is deliberately conservative and high-signal: it fires ONLY the
 * blatant version of the failure — a role policy is present but NOTHING in the
 * working dir grants any resource-policy EFFECT_ALLOW, so the role policy is
 * necessarily being relied on to grant. Subtler per-action mismatches are left
 * to the judge. When no role policy is used the criterion does not apply, so we
 * return a neutral PASS (mirrors synapse-static.js) and never fail unrelated
 * cases.
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
    } else if (/\.ya?ml$/.test(e.name)) {
      acc.push(full);
    }
  }
  return acc;
}

module.exports = (output, context) => {
  const dir = context && context.metadata && context.metadata.workingDir;
  if (!dir || !fs.existsSync(dir)) {
    return { pass: false, score: 0, reason: 'role-policy-grant: no workingDir in metadata' };
  }

  const read = (f) => {
    try { return fs.readFileSync(f, 'utf8'); } catch { return ''; }
  };
  const yamls = walk(dir).map((f) => ({ rel: path.relative(dir, f), text: read(f) }));

  // A role policy is only in play when there's a rolePolicy block with allowActions.
  const roleFiles = yamls.filter(
    (y) => /(^|\n)\s*rolePolicy\s*:/.test(y.text) && /allowActions\s*:/.test(y.text),
  );
  if (roleFiles.length === 0) {
    return {
      pass: true,
      score: 1,
      reason: 'role-policy-grant: no role policy used (criterion N/A) — neutral PASS',
    };
  }

  // A role policy can only narrow, so SOME resource policy must grant EFFECT_ALLOW.
  const grantingResourceFiles = yamls.filter(
    (y) => /(^|\n)\s*resourcePolicy\s*:/.test(y.text) && /EFFECT_ALLOW/.test(y.text),
  );
  if (grantingResourceFiles.length === 0) {
    return {
      pass: false,
      score: 0,
      reason:
        `role-policy-grant: role policy present (${roleFiles.map((r) => r.rel).join(', ')}) but ` +
        'NO resource policy grants any EFFECT_ALLOW — a role policy cannot grant access on its own; ' +
        'a matching resource policy allow is required.',
    };
  }

  return {
    pass: true,
    score: 1,
    reason:
      `role-policy-grant: role policy present and ${grantingResourceFiles.length} resource policy ` +
      'file(s) grant EFFECT_ALLOW (per-action narrowing left to the judge).',
  };
};
