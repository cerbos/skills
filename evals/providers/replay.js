/**
 * promptfoo custom provider for CALIBRATION.
 *
 * Instead of running the agent, it replays a pre-baked, human-labeled fixture
 * (a known-good or known-bad skill output) through the SAME judge rubric used
 * in the real evals. We then assert the judge's verdict matches the human
 * label. If agreement drops, the nightly run is flagged BEFORE any real score
 * is believed — this is the judge-calibration gate.
 *
 * Fixture layout (dir passed via test `vars.fixture`, relative to evals/):
 *   <fixture>/label.json   { "label": "pass"|"fail", "expected": {..criteria..} }
 *   <fixture>/transcript.txt   (optional) baked assistant transcript + tool log
 *   <fixture>/files/           baked "generated" files
 *
 * Output mirrors skill-runner.js so the same rubric prompt applies unchanged.
 */
const fs = require('node:fs');
const path = require('node:path');

const EVAL_ROOT = path.resolve(__dirname, '..');
const MAX_FILE_BYTES = 40_000;

function listFiles(dir, base = dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) listFiles(full, base, acc);
    else acc.push(path.relative(base, full));
  }
  return acc;
}

class CerbosReplayProvider {
  constructor(options = {}) {
    this.config = options.config || {};
    this.providerId = options.id || 'cerbos-replay';
  }

  id() {
    return this.providerId;
  }

  async callApi(_prompt, context) {
    const fixtureRel = (context && context.vars && context.vars.fixture) || this.config.fixture;
    if (!fixtureRel) {
      return { error: 'replay provider: no fixture path in vars.fixture' };
    }
    const fixtureDir = path.resolve(EVAL_ROOT, fixtureRel);
    const filesDir = path.join(fixtureDir, 'files');

    let label = {};
    try {
      label = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'label.json'), 'utf8'));
    } catch (err) {
      return { error: `replay provider: cannot read label.json in ${fixtureRel}: ${err.message}` };
    }

    let transcript = '';
    const tPath = path.join(fixtureDir, 'transcript.txt');
    if (fs.existsSync(tPath)) transcript = fs.readFileSync(tPath, 'utf8');

    const fileBlocks = [];
    for (const rel of listFiles(filesDir).sort()) {
      const buf = fs.readFileSync(path.join(filesDir, rel));
      const body = buf.length > MAX_FILE_BYTES
        ? buf.subarray(0, MAX_FILE_BYTES).toString('utf8') + '\n... [truncated]'
        : buf.toString('utf8');
      fileBlocks.push(`--- ${rel} ---\n${body}`);
    }

    const output = [
      '=== ASSISTANT TRANSCRIPT ===',
      transcript.trim() || '[replayed fixture: no transcript]',
      '',
      '=== GENERATED FILES ===',
      fileBlocks.length ? fileBlocks.join('\n\n') : '[no files]',
    ].join('\n');

    return {
      output,
      metadata: {
        workingDir: filesDir, // deterministic asserts run against the fixture's files
        fixture: fixtureRel,
        humanLabel: label.label,
        expected: label.expected || {},
      },
    };
  }
}

module.exports = CerbosReplayProvider;
