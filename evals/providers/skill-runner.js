/**
 * promptfoo custom provider: run a Cerbos skill in an isolated workspace.
 *
 * For each test case we:
 *   1. make a fresh temp dir,
 *   2. copy the REAL skill source from the repo into `.claude/skills/<name>/`
 *      (so evals always test the live skill, never a drifting copy),
 *   3. optionally seed starting files (for "modify this policy" cases),
 *   4. drive @anthropic-ai/claude-agent-sdk headless with the skill available,
 *   5. return the transcript + the generated files as `output` (so the
 *      llm-rubric judge can see them) and the workspace path in `metadata`
 *      (so deterministic assertions can run `cerbos compile` on real files).
 *
 * Config (from promptfooconfig.yaml `providers[].config`):
 *   skill        - skill to expect firing (e.g. "cerbos-policy"). Both skills
 *                  are always seeded so cross-skill trigger discrimination works.
 *   model        - actor model id. Default env EVAL_ACTOR_MODEL or claude-sonnet-5.
 *   maxTurns     - safety cap. Default 40.
 *   allowedTools - override the tool whitelist.
 */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

// Appended to every eval prompt. The skills are interactive by design (they ask
// clarifying questions and confirm a spec before generating); a one-shot eval
// has no user to answer, so we tell the agent to run autonomously to completion
// and to write into the workspace cwd rather than inventing an absolute path.
const EVAL_DIRECTIVE = `

---
Evaluation-harness instructions: Work autonomously to completion in a single
pass. Do NOT ask clarifying questions or pause to confirm a spec — make
reasonable assumptions and state them briefly. Create ALL files inside the
current working directory (relative paths only; never use /tmp or any absolute
path outside it). Carry out the full workflow, including validation.

Credentials/licences you were not given (e.g. a Cerbos Synapse distribution
repository, registry logins, API keys): do NOT invent real values and do NOT run
commands that require them. Use the documented placeholder (e.g.
CERBOS_DISTRIBUTION_REPO) and state what the user must supply. Still write and
show every config/extension/test file — just don't execute steps that need
credentials you don't have.`;

const REPO_ROOT = path.resolve(__dirname, '..', '..'); // skills repo root
const SKILL_SRC = path.join(REPO_ROOT, 'cerbos'); // cerbos/<skill>/SKILL.md
const ALL_SKILLS = ['cerbos-policy', 'cerbos-synapse-extension'];
const MAX_FILE_BYTES = 40_000; // cap per-file content injected into the judge view

function listFiles(dir, base = dir, acc = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === '.claude' || entry.name === 'node_modules' || entry.name === '.git') continue;
      listFiles(full, base, acc);
    } else {
      acc.push(path.relative(base, full));
    }
  }
  return acc;
}

class CerbosSkillRunner {
  constructor(options = {}) {
    this.config = options.config || {};
    this.providerId = options.id || `cerbos-skill-runner:${this.config.skill || 'all'}`;
  }

  id() {
    return this.providerId;
  }

  async callApi(prompt, context) {
    // vars.skill lets a single provider check either skill's firing (trigger evals);
    // otherwise the provider's configured skill is the one expected to fire.
    const skill = (context && context.vars && context.vars.skill) || this.config.skill;
    const model = this.config.model || process.env.EVAL_ACTOR_MODEL || 'claude-sonnet-5';
    const maxTurns = this.config.maxTurns || 40;
    const allowedTools = this.config.allowedTools || [
      'Read', 'Write', 'Edit', 'MultiEdit', 'Bash', 'Glob', 'Grep', 'Skill', 'Task', 'WebFetch',
    ];

    const workDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cerbos-eval-'));

    // 1. Seed the real skills so the agent can discover + load them.
    for (const name of ALL_SKILLS) {
      const src = path.join(SKILL_SRC, name);
      const dst = path.join(workDir, '.claude', 'skills', name);
      fs.mkdirSync(path.dirname(dst), { recursive: true });
      fs.cpSync(src, dst, { recursive: true });
    }

    // 2. Optionally seed starting files (relative path -> contents) for modify cases.
    const seedFiles = (context && context.vars && context.vars.seedFiles) || this.config.seedFiles;
    const seededPaths = new Set();
    if (seedFiles && typeof seedFiles === 'object') {
      for (const [rel, contents] of Object.entries(seedFiles)) {
        const dst = path.join(workDir, rel);
        fs.mkdirSync(path.dirname(dst), { recursive: true });
        fs.writeFileSync(dst, String(contents));
        seededPaths.add(rel);
      }
    }

    let transcript = '';
    const toolCalls = [];
    let durationMs = null;
    let costUsd = null;
    let errorMsg = null;

    try {
      const { query } = await import('@anthropic-ai/claude-agent-sdk');
      for await (const message of query({
        prompt: prompt + EVAL_DIRECTIVE,
        options: {
          cwd: workDir,
          model,
          maxTurns,
          allowedTools,
          permissionMode: 'bypassPermissions',
          settingSources: ['project'],
        },
      })) {
        if (message.type === 'assistant' && message.message && Array.isArray(message.message.content)) {
          for (const block of message.message.content) {
            if (block.type === 'text' && block.text) transcript += block.text + '\n';
            if (block.type === 'tool_use') {
              toolCalls.push({ name: block.name, input: block.input });
            }
          }
        } else if (message.type === 'result') {
          durationMs = message.duration_ms ?? null;
          costUsd = message.total_cost_usd ?? null;
          if (message.subtype && message.subtype !== 'success') {
            errorMsg = `agent result subtype: ${message.subtype}`;
          }
        }
      }
    } catch (err) {
      errorMsg = `agent run threw: ${err && err.message ? err.message : String(err)}`;
    }

    // 3. Collect the final workspace state (skill fixtures excluded). Seed files
    //    are INCLUDED so "modify this policy" cases show the agent's edits.
    const generated = listFiles(workDir).filter((rel) => !rel.startsWith('.claude/'));

    const fileBlocks = [];
    for (const rel of generated.sort()) {
      let body;
      try {
        const buf = fs.readFileSync(path.join(workDir, rel));
        body = buf.length > MAX_FILE_BYTES
          ? buf.subarray(0, MAX_FILE_BYTES).toString('utf8') + `\n... [truncated ${buf.length - MAX_FILE_BYTES} bytes]`
          : buf.toString('utf8');
      } catch {
        body = '[unreadable]';
      }
      fileBlocks.push(`--- ${rel} ---\n${body}`);
    }

    const skillInvoked = toolCalls.some(
      (t) => t.name === 'Skill' && JSON.stringify(t.input || {}).includes(skill),
    ) || toolCalls.some(
      (t) => t.name === 'Read' && String((t.input && t.input.file_path) || '').includes(`skills/${skill}/SKILL.md`),
    );

    const toolLog = toolCalls
      .map((t) => {
        if (t.name === 'Bash') return `Bash: ${(t.input && t.input.command) || ''}`;
        if (t.name === 'Skill') return `Skill: ${JSON.stringify(t.input)}`;
        if (t.name === 'Read') return `Read: ${(t.input && t.input.file_path) || ''}`;
        if (t.name === 'Write' || t.name === 'Edit') return `${t.name}: ${(t.input && t.input.file_path) || ''}`;
        return t.name;
      })
      .join('\n');

    const output = [
      '=== ASSISTANT TRANSCRIPT ===',
      transcript.trim() || '[no assistant text]',
      '',
      '=== TOOL CALLS ===',
      toolLog || '[no tool calls]',
      '',
      '=== GENERATED FILES ===',
      fileBlocks.length ? fileBlocks.join('\n\n') : '[no files generated]',
    ].join('\n');

    return {
      output,
      tokenUsage: {},
      cost: costUsd ?? undefined,
      metadata: {
        workingDir: workDir,
        skill,
        skillInvoked,
        toolCalls,
        generatedFiles: generated,
        durationMs,
        costUsd,
        error: errorMsg,
      },
    };
  }
}

module.exports = CerbosSkillRunner;
