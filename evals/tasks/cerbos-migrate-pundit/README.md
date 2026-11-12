# cerbos-migrate-pundit

Translate a Rails app's Pundit policies into Cerbos policies with a native test
suite, matching what `authorize` allows for every user, document and controller
action. The [instruction](instruction.md) fixes how `Current.user` and a
`Document` map onto a CheckResources request (a fixed `anonymous` principal for
signed-out visitors; `suspended` and `locked_by` present only when set) and
names one action per controller action. It does not say where the translation
goes wrong.

The seed in `environment/app/` is `ApplicationPolicy` and `DocumentPolicy`, the
controller that calls them, and `schema.md` describing the fields:

| Pundit source | Trap in a direct translation |
| --- | --- |
| `ApplicationPolicy#initialize` raises for `user&.suspended?` | Applies to every query, admins included. `suspended` is optional: an unguarded `P.attr.suspended == true` DENY is skipped under default evaluation but errors under strict evaluation, denying every action to every other user. |
| `new?` calls `create?`, `edit?` calls `update?`, `alias_method :publish?, :update?` | Three actions that never appear as methods in `DocumentPolicy`; each must carry exactly its target's rules. |
| `show?`: `return true if admin?`, then `return false if external? && record.confidential` | An early return that overrides every later grant, including published. A `roles: ["external"]` DENY only denies the external role, so an editor who is also external still sees the team's confidential drafts. It needs `roles: ["*"]` with `"external" in P.roles`, and must exclude admins. |
| `owner?` tests no role | An owner with a role the policies never name (`intern`) may show, update, publish and destroy their own draft. A derived role with named `parentRoles` refuses them. |
| `member_of?` reads `user.team_ids`, guarded by `user.present?` | Guests carry no attributes. An unguarded `R.attr.team_id in P.attr.team_ids` errors under strict evaluation and takes the guest's `show` of a published document with it. |
| `locked_by_someone_else?` | `locked_by` is optional; the update rule needs `!has(R.attr.locked_by) \|\| R.attr.locked_by == P.id`, and admins bypass the lock because `admin?` returns first. |
| `destroy?` | Owner of an unpublished document, or admin; team editors cannot. |

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl and CA certificates, and copies the seed to
`/workspace/app`. Ruby is not installed in the image. Cerbos runs natively.
Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and 180
seconds for verification.

## Verification

| Stage | Requirement |
| --- | --- |
| `compile_normal` | Native compilation and tests pass. |
| `generated_tests` | Every executed, passing `document` assertion agrees with `contract.py`'s Pundit model. Tests run without a `strictEvaluation` option include an external user holding another role denied `show` that the other role alone would be allowed, a suspended admin denied, an owner whose roles the policies never name allowed `update`, `publish` or `destroy`, and `publish` allowed to someone who is neither admin nor owner. |
| `compile_strict` | Compilation and tests also pass with strict evaluation. |
| `pdp_decisions` | 2112 verifier-owned requests (11 principals, including admin+external, editor+external, an unnamed `intern` role with no teams, two suspended accounts and the guest, × 192 documents: 6 owners × 2 teams × published × confidential × `locked_by` absent or one of three users), 7 actions each, against normal and strict PDPs: 14784 decisions per mode. |

Each stage reports a binary score; overall `reward` is 1 only when all four
pass. `tests/contract.py` models the Ruby; `check_resources.py` builds the
matrix from it at run time (`python tests/contract.py` prints a summary).

The model was checked against the real Ruby policies at build time, not in the
task image: `python tests/contract.py --ruby-cases` emits every decision as a
user, record and query with its expected result, and the script below loads
the seed policies with a minimal `Pundit::NotAuthorizedError` and ActiveSupport's
`present?`, and replays them (0 mismatches over 14784 decisions under Ruby
3.3.6):

```bash
python tests/contract.py --ruby-cases > /tmp/cases.jsonl
ruby check.rb "$PWD/environment/app" /tmp/cases.jsonl
```

```ruby
require "json"

class Object
  def present? = !(nil? || (respond_to?(:empty?) && empty?) || self == false)
end

module Pundit
  class NotAuthorizedError < StandardError; end
end

User = Struct.new(:id, :roles, :team_ids, :suspended, keyword_init: true) do
  def suspended? = suspended
end
Document = Struct.new(:id, :owner_id, :team_id, :published, :confidential, :locked_by, keyword_init: true)

app = ARGV.fetch(0)
require File.join(app, "policies/application_policy")
require File.join(app, "policies/document_policy")

mismatches = 0
total = 0
File.foreach(ARGV.fetch(1)) do |line|
  c = JSON.parse(line)
  user = c["user"] && User.new(**c["user"].transform_keys(&:to_sym))
  record = Document.new(**c["record"].transform_keys(&:to_sym))
  result =
    begin
      DocumentPolicy.new(user, record).public_send("#{c["action"]}?") ? true : false
    rescue Pundit::NotAuthorizedError
      false
    end
  total += 1
  next if result == c["expected"]

  mismatches += 1
  warn "MISMATCH #{c["action"]} user=#{c["user"].inspect} record=#{c["record"].inspect} ruby=#{result}" if mismatches <= 10
end
puts "#{total} decisions, #{mismatches} mismatches"
exit(mismatches.zero? ? 0 : 1)
```

## Validated locally

The oracle reference scores reward 1 and an empty workspace scores 0, running
the verifier against Cerbos 0.55.0. These hand-made mutations of the reference
each score 0:

- external DENY scoped to `roles: ["external"]`: `compile_normal`,
  `generated_tests` and `pdp_decisions` fail;
- external DENY without the admin exclusion: `pdp_decisions` fails for
  admin+external;
- suspended DENY without a `has()` guard: `compile_strict` and strict-mode
  `pdp_decisions` fail for every other user;
- team membership without a `has()` guard: strict-mode `pdp_decisions` fails
  for the guest's `show` of published documents;
- owner derived role with named `parentRoles`: `pdp_decisions` fails for the
  `intern` owner;
- `publish` left off the update rule: `pdp_decisions` fails.

## Layout

```text
instruction.md            Agent-facing request
task.toml                 Identity, limits and artifacts
environment/Dockerfile    Pinned runtime; copies the Pundit seed
environment/app/          policies, controllers and schema.md
solution/solve.sh         Installs the reference bundle
solution/policies/        document resource policy, derived roles, suite, fixtures
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/contract.py         Pundit model; builds the decision matrix and Ruby replay cases
tests/check_outputs.py    Native test agreement and coverage
tests/check_resources.py  Starts PDPs and compares decisions
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-pundit -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-pundit -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-pundit \
  --skill ./skills/cerbos-authz-migration --skill ./skills/cerbos-policy \
  -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
