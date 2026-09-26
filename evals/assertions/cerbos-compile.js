/**
 * Deterministic ground-truth check for cerbos-policy outputs.
 * Runs the real Cerbos compiler (which also executes any bundled *_test.yaml)
 * against the exact files the agent produced. We do NOT trust the agent's own
 * self-reported compile result — we run it ourselves.
 *
 * PASS  = `cerbos compile` exits 0 (policies valid AND bundled tests pass)
 * FAIL  = non-zero exit, no policies found, or docker unavailable.
 */
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');

const IMAGE = process.env.CERBOS_IMAGE || 'ghcr.io/cerbos/cerbos:latest';

module.exports = (output, context) => {
  const dir = context && context.metadata && context.metadata.workingDir;
  if (!dir || !fs.existsSync(dir)) {
    return { pass: false, score: 0, reason: 'cerbos-compile: no workingDir in provider metadata' };
  }

  // Guard: are there any policy-looking YAML files at all?
  const hasYaml = execFileSyncSafe('bash', [
    '-lc',
    `find ${JSON.stringify(dir)} -name '*.yaml' -o -name '*.yml' | head -1`,
  ]);
  if (!hasYaml.trim()) {
    return { pass: false, score: 0, reason: 'cerbos-compile: no YAML files were generated' };
  }

  try {
    const out = execFileSync(
      'docker',
      ['run', '--rm', '-v', `${dir}:/policies`, IMAGE, 'compile', '/policies'],
      { stdio: 'pipe', timeout: 180_000 },
    );
    return {
      pass: true,
      score: 1,
      reason: `cerbos compile succeeded${out.toString().trim() ? ': ' + out.toString().trim().slice(0, 300) : ''}`,
    };
  } catch (err) {
    const stderr = (err.stderr && err.stderr.toString()) || '';
    const stdout = (err.stdout && err.stdout.toString()) || '';
    const detail = (stderr || stdout || err.message || '').trim().slice(0, 800);
    return { pass: false, score: 0, reason: `cerbos compile failed: ${detail}` };
  }
};

function execFileSyncSafe(cmd, args) {
  try {
    return execFileSync(cmd, args, { stdio: 'pipe', timeout: 30_000 }).toString();
  } catch {
    return '';
  }
}
