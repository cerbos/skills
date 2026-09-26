/**
 * Deterministic check for the `conditional-deny-fails-open` failure mode.
 *
 * Cerbos: a CEL runtime error in a rule condition is treated as "not
 * satisfied". ALLOW rules fail CLOSED (no match); DENY rules fail OPEN (the
 * deny is skipped) so a matching ALLOW still grants. A security-critical DENY
 * gated on an UNGUARDED reference to a possibly-absent attribute is therefore a
 * fail-open hole whenever a broader ALLOW (that does not depend on the same
 * attribute) would grant the action.
 *
 * This assertion only ENGAGES when the user's request signals that an
 * attribute can be absent/messy (mirrors judge.js reading context.vars.request)
 * — every other policy case is a neutral PASS, so it never fails unrelated
 * cases. When engaged it FAILS only on the precise hole: an EFFECT_DENY whose
 * condition references an attribute NOT guarded by has(), where some EFFECT_ALLOW
 * for the same action does not reference that attribute (and so would still
 * grant when it is missing). A deny that guards with has(), a deny with no
 * attribute condition, or a restriction enforced purely on the allow side all
 * PASS.
 */
const fs = require('node:fs');
const path = require('node:path');
const yaml = require('js-yaml');

const ABSENCE_SIGNAL = /\b(absent|missing|omitted|unset|messy|sometimes\s+missing|may\s+be\s+missing|may\s+not\s+be\s+set|not\s+always\s+(?:set|present)|isn'?t\s+always\s+(?:set|present)|fail[\s-]?safe)\b/i;

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

// Flatten a Cerbos condition `match` node into its expr strings.
function collectExprs(node, acc = []) {
  if (!node || typeof node !== 'object') return acc;
  if (typeof node.expr === 'string') acc.push(node.expr);
  for (const k of ['all', 'any', 'none']) {
    const of = node[k] && node[k].of;
    if (Array.isArray(of)) for (const child of of) collectExprs(child, acc);
  }
  return acc;
}

function ruleExprs(rule) {
  if (!rule || !rule.condition || !rule.condition.match) return [];
  return collectExprs(rule.condition.match);
}

// Attribute names referenced in a set of exprs.
function attrRefs(text) {
  const re = /(?:request\.resource\.attr|request\.principal\.attr|R\.attr|P\.attr)\.([A-Za-z_][A-Za-z0-9_]*)/g;
  const names = new Set();
  let m;
  while ((m = re.exec(text)) !== null) names.add(m[1]);
  return names;
}

function isGuarded(text, name) {
  // has(...attr.NAME) anywhere in the rule's condition text.
  return new RegExp(`has\\([^)]*\\.attr\\.${name}\\b`).test(text);
}

function actionsOf(rule) {
  const a = rule && rule.actions;
  if (Array.isArray(a)) return a;
  if (typeof a === 'string') return [a];
  return [];
}

function actionMatch(ruleActions, action) {
  return ruleActions.includes(action) || ruleActions.includes('*') || action === '*';
}

module.exports = (output, context) => {
  const dir = context && context.metadata && context.metadata.workingDir;
  const request = (context && context.vars && context.vars.request) || '';

  // Only engage when the request tells us an attribute can be absent/malformed.
  if (!ABSENCE_SIGNAL.test(request)) {
    return { pass: true, score: 1, reason: 'conditional-deny-fails-open: request does not signal a possibly-absent attribute (deferred to judge)' };
  }
  if (!dir || !fs.existsSync(dir)) {
    return { pass: true, score: 1, reason: 'conditional-deny-fails-open: no workingDir (deferred to judge)' };
  }

  const policies = [];
  for (const f of walk(dir)) {
    if (/_test\.ya?ml$/.test(f)) continue;
    let docs;
    try { docs = yaml.loadAll(fs.readFileSync(f, 'utf8')); } catch { continue; }
    for (const d of docs) {
      if (d && d.resourcePolicy && Array.isArray(d.resourcePolicy.rules)) {
        policies.push({ file: path.relative(dir, f), rp: d.resourcePolicy });
      }
    }
  }
  if (policies.length === 0) {
    return { pass: true, score: 1, reason: 'conditional-deny-fails-open: no resource policies found (deferred to judge)' };
  }

  const holes = [];
  for (const { file, rp } of policies) {
    const rules = rp.rules;
    const allows = rules.filter((r) => r.effect === 'EFFECT_ALLOW');
    const denies = rules.filter((r) => r.effect === 'EFFECT_DENY');

    for (const deny of denies) {
      const text = ruleExprs(deny).join('\n');
      if (!text) continue; // deny with no attribute condition — robust.
      const unguarded = [...attrRefs(text)].filter((n) => !isGuarded(text, n));
      if (unguarded.length === 0) continue; // every referenced attr guarded with has().

      for (const action of actionsOf(deny)) {
        // A competing ALLOW for this action that does NOT reference any of the
        // unguarded attrs would still grant when the attr is missing → hole.
        const competing = allows.find((a) => {
          if (!actionMatch(actionsOf(a), action)) return false;
          const aText = ruleExprs(a).join('\n');
          const aAttrs = attrRefs(aText);
          return !unguarded.some((n) => aAttrs.has(n));
        });
        if (competing) {
          holes.push(`${file}: DENY "${deny.name || '(unnamed)'}" on "${action}" references unguarded attr(s) [${unguarded.join(', ')}] while ALLOW "${competing.name || '(unnamed)'}" would still grant when absent`);
        }
      }
    }
  }

  if (holes.length > 0) {
    return {
      pass: false,
      score: 0,
      reason: `conditional-deny-fails-open: security-critical DENY can fail open — ${holes.join('; ')}. Guard the attribute with has() or enforce the restriction on the ALLOW side.`,
    };
  }
  return {
    pass: true,
    score: 1,
    reason: 'conditional-deny-fails-open: no unguarded fail-open DENY (denies are attribute-free, has()-guarded, or restriction is allow-side)',
  };
};
