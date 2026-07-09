/**
 * LLM-as-judge assertion (runs inside promptfoo as a `javascript` assert).
 *
 * Design goals, per the calibration guidance:
 *   - Narrow, binary criteria (one named failure mode each) — not fuzzy scores.
 *   - The SAME judge implementation runs real evals and calibration, so the
 *     thing we calibrate is exactly the thing we score with.
 *
 * Two modes, chosen automatically:
 *   - Real eval: no `metadata.expected`. PASS = every scoped criterion PASSes.
 *   - Calibration: `metadata.expected` present (replayed labeled fixture).
 *     PASS = the judge's verdict MATCHES the human label on every scoped
 *     criterion. A miss here means the judge is untrustworthy → run flagged.
 *
 * Scope: judges all criteria for the skill unless `context.vars.criteria`
 * lists a subset of ids (some cases don't exercise every failure mode).
 *
 * Config: judge model via env EVAL_JUDGE_MODEL (default claude-haiku-4-5).
 * Auth: ANTHROPIC_API_KEY.
 */
const fs = require('node:fs');
const path = require('node:path');

const JUDGE_MODEL = process.env.EVAL_JUDGE_MODEL || 'claude-haiku-4-5-20251001';
const API_URL = 'https://api.anthropic.com/v1/messages';

function loadCriteria(skill) {
  const p = path.join(__dirname, '..', 'criteria', `${skill}.json`);
  return JSON.parse(fs.readFileSync(p, 'utf8')).criteria;
}

async function callJudge(output, criteria) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY not set');

  const criteriaText = criteria
    .map((c, i) => `${i + 1}. id="${c.id}"\n   Failure mode: ${c.failureMode}\n   Decide: ${c.question}`)
    .join('\n\n');

  const system =
    'You are a strict, literal grader for AI-generated engineering artifacts. ' +
    'You are given the material an agent produced (its transcript, tool calls, and generated files) ' +
    'and a list of narrow pass/fail criteria. For each criterion, decide PASS (the good behaviour holds) ' +
    'or FAIL (the specific named failure mode occurred). Judge ONLY from the provided material — never assume ' +
    'behaviour you cannot see. When evidence is absent for a criterion that requires positive evidence, FAIL it. ' +
    'Return ONLY a JSON array, one object per criterion: ' +
    '[{"id": "<criterion id>", "pass": <true|false>, "reason": "<one sentence citing specific evidence>"}]. No prose.';

  const user =
    `MATERIAL UNDER REVIEW:\n<material>\n${output}\n</material>\n\n` +
    `CRITERIA:\n${criteriaText}\n\n` +
    `Return the JSON array now.`;

  const body = JSON.stringify({
    model: JUDGE_MODEL,
    max_tokens: 1500,
    temperature: 0,
    system,
    messages: [{ role: 'user', content: user }],
  });
  const headers = {
    'content-type': 'application/json',
    'x-api-key': apiKey,
    'anthropic-version': '2023-06-01',
  };

  // Retry transient failures (network drops, 429/5xx) with backoff — under heavy
  // concurrent load the Anthropic API intermittently rate-limits, and an
  // unretried "fetch failed" would wrongly fail the case rather than the skill.
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let res;
  let lastErr;
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      res = await fetch(API_URL, { method: 'POST', headers, body });
      if (res.ok) break;
      if (![429, 500, 502, 503, 529].includes(res.status)) {
        throw new Error(`judge API ${res.status}: ${(await res.text()).slice(0, 300)}`);
      }
      lastErr = new Error(`judge API ${res.status}`);
    } catch (err) {
      lastErr = err; // network error (e.g. "fetch failed")
    }
    await sleep(1000 * Math.pow(2, attempt) + Math.floor(attempt * 250)); // 1s,2s,4s,8s...
    res = null;
  }
  if (!res || !res.ok) throw lastErr || new Error('judge API: exhausted retries');
  const data = await res.json();
  const text = (data.content || []).map((b) => b.text || '').join('');
  const match = text.match(/\[[\s\S]*\]/);
  if (!match) throw new Error(`judge returned non-JSON: ${text.slice(0, 200)}`);
  return JSON.parse(match[0]);
}

module.exports = async (output, context) => {
  const meta = (context && context.metadata) || {};
  const skill = meta.skill || (context && context.vars && context.vars.skill);
  if (!skill) {
    return { pass: false, score: 0, reason: 'judge: could not determine skill' };
  }

  let criteria = loadCriteria(skill);
  const scope = context && context.vars && context.vars.criteria;
  if (Array.isArray(scope) && scope.length) {
    criteria = criteria.filter((c) => scope.includes(c.id));
  }

  // Give the judge the original request so coverage / no-fabrication are judged
  // against what was actually asked, not just what the agent chose to restate.
  // Only prepend it when a request exists — calibration replays carry their
  // requirements in the fixture transcript, and a "(not provided)" line there
  // would wrongly read as "the user specified nothing".
  const request = context && context.vars && context.vars.request;
  const material = request ? `ORIGINAL USER REQUEST:\n${request}\n\n${output}` : output;

  let verdicts;
  try {
    verdicts = await callJudge(material, criteria);
  } catch (err) {
    return { pass: false, score: 0, reason: `judge error: ${err.message}` };
  }
  const byId = Object.fromEntries(verdicts.map((v) => [v.id, v]));

  const expected = meta.expected; // present only in calibration mode
  const calibration = expected && Object.keys(expected).length > 0;

  const components = criteria.map((c) => {
    const v = byId[c.id] || { pass: false, reason: 'judge omitted this criterion' };
    if (calibration) {
      const exp = expected[c.id];
      const agree = typeof exp === 'boolean' ? v.pass === exp : true;
      return {
        pass: agree,
        score: agree ? 1 : 0,
        reason: `[${c.id}] judge=${v.pass} human=${exp} ${agree ? 'MATCH' : 'MISMATCH'} — ${v.reason}`,
      };
    }
    return {
      pass: v.pass === true,
      score: v.pass === true ? 1 : 0,
      reason: `[${c.id}] ${v.pass ? 'PASS' : 'FAIL'} — ${v.reason}`,
    };
  });

  const passed = components.filter((c) => c.pass).length;
  const label = calibration ? 'judge-vs-human agreement' : 'criteria passed';
  return {
    pass: components.every((c) => c.pass),
    score: passed / components.length,
    reason: `judge (${skill}): ${passed}/${components.length} ${label}`,
    componentResults: components,
  };
};
