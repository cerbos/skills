/**
 * Trigger-dimension check (idea borrowed from skill-creator's run_eval.py):
 * did the RIGHT skill actually fire for this prompt?
 *
 * Both skills are seeded in every workspace, so this discriminates:
 *   - "should fire" cases assert metadata.skillInvoked === true
 *   - "should NOT fire" cases (vars.expectSkill: false) assert it stayed silent
 * Control via `vars.expectSkill` (default true).
 */
module.exports = (output, context) => {
  const meta = (context && context.metadata) || {};
  const expect = context && context.vars && context.vars.expectSkill;
  const shouldFire = expect === undefined ? true : Boolean(expect);
  const fired = Boolean(meta.skillInvoked);

  const pass = fired === shouldFire;
  return {
    pass,
    score: pass ? 1 : 0,
    reason: pass
      ? `skill-fired: ${meta.skill} ${fired ? 'fired' : 'stayed silent'} as expected`
      : `skill-fired: expected ${meta.skill} to ${shouldFire ? 'fire' : 'stay silent'} but it ${fired ? 'fired' : 'did not'}`,
  };
};
