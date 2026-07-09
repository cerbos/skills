/**
 * Turn promptfoo JSON output into a compact Markdown summary and append it to
 * $GITHUB_STEP_SUMMARY (or stdout locally). Usage:
 *   node scripts/summary.js "<label>" <results.json> ["<label2>" <results2.json> ...]
 */
const fs = require('node:fs');

function summarize(label, file) {
  let data;
  try {
    data = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (err) {
    return `### ${label}\n\n⚠️ could not read ${file}: ${err.message}\n`;
  }
  const results = (data.results && data.results.results) || data.results || [];
  const stats = (data.results && data.results.stats) || data.stats || {};
  const total = results.length || (stats.successes || 0) + (stats.failures || 0);
  const passed = results.filter((r) => r.success).length || stats.successes || 0;
  const rate = total ? Math.round((passed / total) * 100) : 0;
  const icon = passed === total ? '✅' : '❌';

  let md = `### ${icon} ${label} — ${passed}/${total} passed (${rate}%)\n\n`;

  const failed = results.filter((r) => !r.success);
  if (failed.length) {
    md += '| Case | Failing checks |\n|---|---|\n';
    for (const r of failed) {
      const name =
        (r.testCase && r.testCase.description) ||
        (r.vars && (r.vars.description || r.vars.request || r.vars.fixture)) ||
        r.description ||
        'case';
      const reasons = [];
      const comps =
        (r.gradingResult && r.gradingResult.componentResults) ||
        (r.componentResults) || [];
      for (const c of comps) {
        collectFailures(c, reasons);
      }
      if (!reasons.length && r.gradingResult && r.gradingResult.reason) {
        reasons.push(r.gradingResult.reason);
      }
      const cell = reasons.slice(0, 4).map((s) => s.replace(/\|/g, '\\|')).join('<br>') || 'failed';
      md += `| ${String(name).slice(0, 60)} | ${cell.slice(0, 500)} |\n`;
    }
  } else {
    md += '_All checks passed._\n';
  }
  return md + '\n';
}

function collectFailures(comp, out) {
  if (!comp) return;
  if (comp.componentResults && comp.componentResults.length) {
    for (const c of comp.componentResults) collectFailures(c, out);
  } else if (comp.pass === false && comp.reason) {
    out.push(comp.reason);
  }
}

const args = process.argv.slice(2);
let md = '## Cerbos skills — eval results\n\n';
for (let i = 0; i < args.length; i += 2) {
  md += summarize(args[i], args[i + 1]);
}

const out = process.env.GITHUB_STEP_SUMMARY;
if (out) fs.appendFileSync(out, md);
else process.stdout.write(md);
