# Testing framework (`synapse test`)

Test runner for TDD of custom extensions. Tests are Starlark scripts but exercise **any** extension kind and runtime — Starlark or WASM. Per suite, the runner starts a fresh Synapse instance from the suite's configuration and runs the test functions against it. No `docker compose up`, no `sleep 5`, no curl.

Default way to test extensions — every extension demo should ship a `*_test.star` suite. Bash + curl / Hurl harnesses (see `run-and-test.md`) are alternatives for driving a long-lived deployed instance, as are Testcontainers or CI service containers.

Contents:

- [Running tests](#running-tests) — docker run command, CLI flags
- [Suite and test naming](#suite-and-test-naming)
- [Test outcomes](#test-outcomes)
- [The `test_suite` struct](#the-test_suite-struct) — `synapse_config`, `test_cases`, `SYNAPSE_ROOT`
- [The `testing` module](#the-testing-module)
- [The `context` object](#the-context-object) — one helper per extension entry point
- [Test data files](#test-data-files)
- [Parameterized tests](#parameterized-tests)
- [Loading modules](#loading-modules)
- [Debugging failures](#debugging-failures)
- [Gotchas](#gotchas)

## Running tests

```sh
docker run \
    --rm --name synapse-test \
    -v $(pwd)/config.yaml:/config/config.yaml:ro \
    -v $(pwd)/policies:/policies:ro \
    -v $(pwd)/extensions:/extensions:ro \
    CERBOS_DISTRIBUTION_REPO/synapse/synapse:latest \
    test /extensions
```

- Arguments: directories and/or files. Directories searched **recursively** for files ending in `_test.star`.
- `test --match='^enrich' /tests` — only test cases whose names match the regex.
- `test --output=jsonl /tests` — JSONLines output for scripted processing (default: `console`).
- `test --verbose /tests` — Synapse instance logs + `print()` output from test cases. First stop when debugging.

Output:

```
== PASS:Test principal enrichment (/extensions/enrich_principal_test.star)
   Passed=1 Failed=0 Skipped=0
   --- PASS:enrichment | Assertion is True
```

## Suite and test naming

- Suite files must end in `_test.star` (e.g. `enrich_principal_test.star`).
- Test cases: functions prefixed `test_` taking a single `context` parameter. Anything else ignored — helpers can live in the same file.

```python
def test_always_pass(context):
    return testing.ok("I always pass")

def test_always_fail(context):
    return testing.fail("I always fail")

def helper():   # ignored by the runner — no test_ prefix
    pass
```

## Test outcomes

Return value determines status:

| Return | Status |
|--------|--------|
| Nothing, `True`, or `testing.ok(msg)` | Pass |
| `False`, `testing.fail(msg)`, or any runtime error | Fail |
| `testing.skip(msg)` | Skip |
| `testing.assert(expr)` | Pass if `expr` is truthy, fail otherwise |

## The `test_suite` struct

Optional module-level `test_suite` struct configures the suite:

```python
test_suite = struct(
    name = "Tests for extension foo",                          # default: derived from file name
    synapse_config = testing.load_synapse_config("synapse.yaml"),
    skip = True,                                               # skip the whole suite
    test_cases = { ... },                                      # explicit test list (see below)
)
```

- **`synapse_config`** — configuration for the per-suite instance. Either `testing.load_synapse_config(path)` (a YAML config file as in the configuration reference) or an inline Starlark dict:

  ```python
  test_suite = struct(
      synapse_config = {
          "pdp": {
              "inProcess": {
                  "storage": {
                      "driver": "disk",
                      "disk": {"directory": "${SYNAPSE_ROOT}/policies"}
                  }
              }
          }
      }
  )
  ```

  If omitted, the suite gets a basic server with **no extensions** and an in-process PDP reading policies from a `policies` directory next to the test file — fine for policy smoke tests, useless for exercising extensions. Always set `synapse_config` when testing an extension.

- **`test_cases`** — dict of `name → function`; **overrides implicit `test_` discovery** — only listed functions run. Values: lambdas or references to functions defined *earlier in the file* (Starlark evaluates top-to-bottom — declare before reference):

  ```python
  def always_fail(context):
      return testing.fail("I always fail")

  test_suite = struct(
      synapse_config = testing.load_synapse_config("synapse.yaml"),
      test_cases = {
          "always_pass": lambda context: testing.ok("I always pass"),
          "always_fail": always_fail,
      }
  )
  ```

### Path resolution and `SYNAPSE_ROOT`

Runner sets the working directory **and** the `SYNAPSE_ROOT` environment variable to the test file's directory. So:

- Relative paths in `testing.load_synapse_config(...)` / `testing.load_testdata(...)` resolve relative to the test file.
- Use `${SYNAPSE_ROOT}` inside the Synapse config (file or inline) to reference policies/extensions stored next to the test file.
- Container-absolute paths (e.g. `/config/config.yaml`) also work when bind-mounted, as the quickstart does.

## The `testing` module

Available in every suite without `load()`:

| Function | Description |
|----------|-------------|
| `testing.assert(expression)` | Assert that the expression evaluates to true |
| `testing.compare_equal(expected, actual)` | Deep/proto-aware comparison; returns a result whose message is the diff — pass it to `testing.assert(...)` |
| `testing.load_synapse_config(path)` | Load a Synapse configuration file |
| `testing.load_testdata(path)` | Load a test data file (see below) |
| `testing.ok(message)` | Explicitly mark the test as passed |
| `testing.fail(message)` | Explicitly mark the test as failed |
| `testing.skip(message)` | Explicitly mark the test as skipped |

## The `context` object

Each test function receives a `context` with helpers that send requests to the suite's Synapse instance — one helper per extension entry point:

| Function | Exercises |
|----------|-----------|
| `context.check_resources(request)` | Proxy extensions / data sources via Cerbos CheckResources |
| `context.plan_resources(request)` | Proxy extensions via Cerbos PlanResources |
| `context.access_evaluation(request)` | Proxy extensions via AuthZEN access evaluation |
| `context.access_evaluation_batch(request)` | Proxy extensions via AuthZEN batch evaluation |
| `context.envoy_check(request)` | Envoy ext_authz extensions |
| `context.http_get/post/put/patch/delete/head/options(path, params=None, headers=None, auth=(), body=None, json_body=None, form_body=None, form_encoding="", timeout=30, allow_redirects=True, verify=True)` | Route extensions under `/ext/...` (same signature as the Starlark `http` module) |

Requests built with `struct(...)` mirroring the proto shapes:

```python
test_suite = struct(
    name = "Test principal enrichment",
    synapse_config = testing.load_synapse_config("synapse.yaml"),
)

def test_enrichment(context):
    request = struct(
        requestId = "qs-001",
        principal = struct(id = "1", roles = ["employee"]),
        resources = [
            struct(actions = ["view"],
                   resource = struct(kind = "invoice", id = "inv-42",
                                     attr = {"company": "Romaguera-Crona"})),
            struct(actions = ["view"],
                   resource = struct(kind = "invoice", id = "inv-99",
                                     attr = {"company": "Other Inc"})),
        ]
    )
    have = context.check_resources(request)
    return testing.assert(have.results[0].actions["view"] == "EFFECT_ALLOW"
                          and have.results[1].actions["view"] == "EFFECT_DENY")
```

Other entry points, same pattern:

```python
# Plan
def test_plan(context):
    have = context.plan_resources(struct(
        request_id = "test",
        principal = struct(id = "john", roles = ["employee"]),
        actions = ["view"],
        resource = struct(kind = "invoice")))
    return testing.assert(set(have.actions) == set(["view"])
                          and have.filter.kind == "KIND_CONDITIONAL")

# AuthZEN
def test_access_evaluation(context):
    have = context.access_evaluation(struct(
        subject = struct(type = "user", id = "john",
                         properties = {"cerbos.roles": ["employee"]}),
        resource = struct(type = "invoice", id = "XX125",
                          properties = {"owner": "john"}),
        action = struct(name = "view")))
    return testing.assert(have.decision)

# Envoy ext_authz
def test_envoy_check(context):
    have = context.envoy_check(struct(
        attributes = struct(
            source = struct(principal = "spiffe://cerbos.dev/cerbie"),
            request = struct(http = struct(id = "foo", method = "GET",
                                           path = "/foo?op=check_response")))))
    return testing.assert(have.status.code == 0)

# Route extension
def test_route(context):
    have = context.http_get("/ext/foo", {"op": "http_response"})
    return testing.assert(have.status_code == 200 and have.body() == "Welcome")
```

## Test data files

Reuse common requests/responses from a YAML or JSON file:

```yaml
# check-resources-test-data.yaml
testData:                       # required root key
  req_john:                     # identifier you reference in the script
    checkResourcesRequest:      # data type — see table below
      requestId: "john"
      principal:
        id: "john"
        roles: ["employee"]
      resources:
        - resource:
            id: "XX125"
            kind: "invoice"
            attr: {owner: "john", department: "Music", geography: "GB"}
          actions: ["view"]
  resp_john:
    checkResourcesResponse:
      requestId: "john"
      results:
        - resource: {id: "XX125", kind: "invoice"}
          actions: {view: EFFECT_ALLOW}
```

```python
testdata = testing.load_testdata("check-resources-test-data.yaml")  # global → shared across tests

def test_external_test_data(context):
    have = context.check_resources(testdata["req_john"])
    want = testdata["resp_john"]
    return testing.assert(have.results[0].actions["view"] == want.results[0].actions["view"])
```

Supported data types: `checkResourcesRequest` / `checkResourcesResponse`, `planResourcesRequest` / `planResourcesResponse`, `authzenEvaluationRequest` / `authzenEvaluationResponse`, `authzenEvaluationBatchRequest` / `authzenEvaluationBatchResponse`, `envoyCheckRequest` / `envoyCheckResponse`, `httpRequest` / `httpResponse` (proto schemas on buf.build under `cerbos/cerbos-api` and `envoyproxy/envoy`).

## Parameterized tests

Generate test cases programmatically — e.g. pair `req_*`/`resp_*` entries from a test data file:

```python
def build_test_case(request, expected):
    def test_case(context):
        actual = context.check_resources(request)
        for (i, expected_result) in enumerate(expected.results):
            for (action, expected_effect) in dict(expected_result.actions).items():
                if actual.results[i].actions[action] != expected_effect:
                    return testing.fail("Action {} of result {} should be {} but is {}".format(
                        action, i, expected_effect, actual.results[i].actions[action]))
    return test_case

def build_test_case_list():
    testdata = testing.load_testdata("check-resources-test-data.yaml")
    test_cases = {}
    for (name, data) in testdata.items():
        if name.startswith("req_"):
            test_name = name.removeprefix("req_")
            expected_resp = testdata.get("resp_" + test_name)
            if expected_resp:
                test_cases[test_name] = build_test_case(data, expected_resp)
    return test_cases

test_suite = struct(
    name = "CheckResources tests",
    synapse_config = testing.load_synapse_config("synapse.yaml"),
    test_cases = build_test_case_list(),
)
```

## Loading modules

Standard loadable Starlark modules (`re`, `json`, `http`, `base64`, ... — see `starlark-environment.md`) available in test scripts via `load`:

```python
load("re", "re")

def test_regex(context):
    return testing.assert(re.match("f.*", "foo"))
```

## Debugging failures

1. `test --verbose ...` — Synapse logs + `print()` output.
2. Load the test script into the REPL and call its functions by hand:

   ```sh
   docker run -v $(pwd):/tests:ro \
       CERBOS_DISTRIBUTION_REPO/synapse/synapse:latest \
       starlark repl /tests/fail_test.star
   ```

   Real `context` object isn't available in the REPL — decouple the logic you want to debug from the framework and pass mock data.

## Gotchas

- **Declare before reference.** Starlark evaluates top-to-bottom; a function referenced in `test_suite.test_cases` must be defined above the `test_suite` assignment.
- **`test_cases` disables discovery.** Once set, `test_` prefixed functions not listed in it will *not* run.
- **No extensions by default.** A suite without `synapse_config` starts a bare PDP — your extension won't be loaded and tests will pass/fail against vanilla policy evaluation.
- **Proto maps in responses** behave as everywhere else in Starlark Synapse: use `"key" in map` / `map["key"]`, not `.get()`; wrap in `dict(...)` to iterate `.items()`.
