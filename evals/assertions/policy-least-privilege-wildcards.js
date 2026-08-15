/**
 * Deterministic least-privilege check for cerbos-policy outputs.
 *
 * Cerbos flags "overly broad wildcards": a rule using actions:['*'] or
 * roles:['*'] matches more than intended (docs: policies/debugging.adoc —
 * "Common causes of unexpected ALLOW"). roles:['*'] disregards roles entirely
 * (docs: policies/resource_policies.adoc — "The special value `*` can be used
 * to disregard roles when evaluating the rule"). On an EFFECT_ALLOW rule that
 * is a least-privilege violation; on an EFFECT_DENY rule a blanket wildcard is
 * safe/encouraged (it only narrows access).
 *
 * This check flags the unambiguous over-broad case only: an EFFECT_ALLOW rule
 * that grants roles:['*'] with NO condition to scope it — i.e. every principal
 * is granted the action unconditionally. Wildcard ALLOWs that ARE scoped by a
 * condition (the documented JWT-audience pattern) and actions:['*'] bound to a
 * specific role/derived role are deferred to the judge, which can see whether
 * the user actually asked for that breadth.
 *
 * Neutral PASS when no resource policies are present or none contain an
 * unconditional wildcard-role ALLOW, so unrelated cases are never failed.
 */
const fs = require('node:fs');
const path = require('node:path');

function safeRead(f) {
  try { return fs.readFileSync(f, 'utf8'); } catch { return ''; }
}

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (['.claude', '.git', 'node_modules'].includes(e.name)) continue;
      walk(full, acc);
    } else if (/\.ya?ml$/.test(e.name) && !/_test\.ya?ml$/.test(e.name)) {
      acc.push(full);
    }
  }
  return acc;
}

// Split a resource policy's `rules:` list into individual rule-block texts.
function ruleBlocks(text) {
  const lines = text.split('\n');
  let i = lines.findIndex((l) => /^\s*rules:\s*(#.*)?$/.test(l));
  if (i < 0) return [];
  const rulesIndent = lines[i].match(/^(\s*)/)[1].length;
  const blocks = [];
  let cur = null;
  for (i += 1; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*$/.test(line)) { if (cur) cur.push(line); continue; }
    const indent = line.match(/^(\s*)/)[1].length;
    if (indent <= rulesIndent) break; // dedented out of the rules list
    if (/^\s*-\s/.test(line)) {
      if (cur) blocks.push(cur.join('\n'));
      cur = [line];
    } else if (cur) {
      cur.push(line);
    }
  }
  if (cur) blocks.push(cur.join('\n'));
  return blocks;
}

function rolesHasWildcard(block) {
  // inline form:  roles: ["*"]  or  roles: ['*', ...]
  const inline = block.match(/\broles:\s*(\[[^\]]*\])/);
  if (inline) return /['"]\*['"]/.test(inline[1]) || /\[\s*\*\s*\]/.test(inline[1]);
  // block form:
  //   roles:
  //     - "*"
  const m = block.match(/\broles:\s*(?:#.*)?\n([\s\S]*?)(?=\n\s*[A-Za-z_][\w-]*:|$)/);
  if (m) return /^\s*-\s*['"]?\*['"]?\s*(?:#.*)?$/m.test(m[1]);
  return false;
}

module.exports = (output, context) => {
  const dir = context && context.metadata && context.metadata.workingDir;
  if (!dir || !fs.existsSync(dir)) {
    return { pass: true, score: 1, reason: 'least-privilege-wildcards: no workingDir (N/A)' };
  }

  const files = walk(dir).filter((f) => /resourcePolicy\s*:/.test(safeRead(f)));
  if (files.length === 0) {
    return { pass: true, score: 1, reason: 'least-privilege-wildcards: no resource policies (N/A)' };
  }

  const violations = [];
  for (const f of files) {
    const text = safeRead(f);
    const rel = path.relative(dir, f);
    for (const block of ruleBlocks(text)) {
      const isAllow = /\beffect:\s*EFFECT_ALLOW\b/.test(block);
      if (!isAllow) continue;
      const hasCondition = /\bcondition:/.test(block);
      if (rolesHasWildcard(block) && !hasCondition) {
        const nameMatch = block.match(/\bname:\s*(.+)/);
        const label = nameMatch ? nameMatch[1].trim() : block.split('\n')[0].trim();
        violations.push(`${rel}: EFFECT_ALLOW rule "${label}" grants roles:["*"] with no condition`);
      }
    }
  }

  if (violations.length) {
    return {
      pass: false,
      score: 0,
      reason: `least-privilege-wildcards: over-broad wildcard ALLOW — ${violations.join('; ')}`,
    };
  }
  return {
    pass: true,
    score: 1,
    reason: 'least-privilege-wildcards: no unconditional wildcard-role EFFECT_ALLOW rules',
  };
};
