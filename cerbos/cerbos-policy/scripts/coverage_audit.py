#!/usr/bin/env python3
"""Check that a Cerbos test run covers a saved coverage plan.

Usage:
    python3 coverage_audit.py --policies DIR --plan coverage-plan.json \
        --report normal.json [--report strict.json]

Each report is the stdout of `cerbos compile --output=json DIR` (add
`--strict-evaluation` for the strict report). The plan is JSON:

    {
      "paths": [
        {"id": "document-owner", "kind": "document",
         "requires": ["parent-role", "tenant", "ownership"]}
      ],
      "rows": [
        {"id": "document-owner-edit", "principal": "alice_employee",
         "resource": "document_owned_by_alice", "action": "edit",
         "effect": "EFFECT_ALLOW"},
        {"id": "document-missing-parent-role-edit",
         "principal": "alice_reviewer_only",
         "resource": "document_owned_by_alice", "action": "edit",
         "effect": "EFFECT_DENY", "control": "document-owner-edit",
         "change": "principal.roles", "path": "document-owner",
         "prerequisite": "parent-role",
         "facts": {"resource.attr.owner": "alice"}}
      ]
    }

`principal` and `resource` are fixture keys. `control` names a row with the
opposite effect, `change` the one request field that differs from it, `path`
and `prerequisite` the grant-path requirement the row isolates, and `facts`
values the resolved request must have (null for an absent attribute).
Optional row fields: `suite` (test file path relative to DIR) and `test`
(test case name) narrow the match. Field paths are `principal.id`,
`principal.roles`, `principal.attr.<name>`, `principal.scope`,
`principal.policyVersion`, `resource.kind`, `resource.attr.<name>`,
`resource.scope` and `resource.policyVersion`. `resource.id` is ignored when
comparing a row with its control.

For every row the audit requires an executed, passing assertion with the
planned effect in every report. For a row with a control it also requires the
control to have the opposite effect, the same action and resource kind, and
resolved requests that differ at exactly the named field, and the resolved
request to have every value listed in `facts`. For every declared
path it requires, for each listed prerequisite, a passing row with that `path`,
`prerequisite` and a control, against a resource of the path's kind. For every
role named by a scoped resource-policy rule or scoped role policy it requires,
in that scope and in each descendant scope with its own policy, a passing row
for a principal with that role whose `change` is `resource.scope` and whose
effect flips. The other side is a scope in a sibling branch when one exists,
otherwise the unscoped base. The plan's `scopeExemptions` can list a scope and
role with a reason instead.

Needs only the Python 3 standard library. Fixtures and suites are read with
PyYAML when it is installed, otherwise with a built-in reader for the YAML
subset they use. Exits 1 when coverage fails and 2 when an input cannot be
read, such as YAML with anchors, aliases or tags without PyYAML.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ABSENT = "<absent>"
EFFECTS = {"EFFECT_ALLOW", "EFFECT_DENY"}
FIELD = re.compile(r"(principal\.(id|roles|scope|policyVersion|attr\..+)|resource\.(id|kind|scope|policyVersion|attr\..+))")
FIELDS = (
    "principal.id, principal.roles, principal.attr.<name>, principal.scope, principal.policyVersion, "
    "resource.kind, resource.attr.<name>, resource.scope or resource.policyVersion"
)


class Unreadable(Exception):
    """An input file the audit cannot read."""


if yaml:
    class _Loader(yaml.SafeLoader):
        """SafeLoader that keeps dates as strings, as Cerbos does."""

    _Loader.yaml_implicit_resolvers = {
        first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
        for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }


NULLS = {"", "~", "null", "Null", "NULL"}
TRUES = {"true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"}
FALSES = {"false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF"}
INT = re.compile(r"[-+]?(?:0|[1-9][0-9_]*)$")
FLOAT = re.compile(r"[-+]?(?:[0-9][0-9_]*\.[0-9_]*|\.[0-9_]+)(?:[eE][-+][0-9]+)?$")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "/": "/", "\\": "\\", '"': '"', " ": " "}


def scalar(text):
    """Resolve a plain scalar the way PyYAML's SafeLoader does, minus dates."""
    if text in NULLS:
        return None
    if text in TRUES:
        return True
    if text in FALSES:
        return False
    if INT.match(text):
        return int(text.replace("_", ""))
    if FLOAT.match(text):
        return float(text.replace("_", ""))
    return text


def quoted(text, pos):
    """Parse a quoted scalar starting at text[pos]; return (value, next position)."""
    quote, pos, out = text[pos], pos + 1, []
    while pos < len(text):
        char = text[pos]
        if quote == "'" and char == "'":
            if text[pos + 1:pos + 2] == "'":
                out.append("'")
                pos += 2
                continue
            return "".join(out), pos + 1
        if quote == '"' and char == '"':
            return "".join(out), pos + 1
        if quote == '"' and char == "\\":
            code = text[pos + 1:pos + 2]
            if code == "u":
                out.append(chr(int(text[pos + 2:pos + 6], 16)))
                pos += 6
                continue
            if code not in ESCAPES:
                raise ValueError(f"unsupported escape \\{code}")
            out.append(ESCAPES[code])
            pos += 2
            continue
        out.append(char)
        pos += 1
    raise ValueError("unterminated quoted string")


def opens_quote(text, pos):
    """A quote opens a quoted scalar only at the start of a token."""
    return text[pos] in "'\"" and (pos == 0 or text[pos - 1] in " \t[{,:-")


def closes_quote(text, pos, quote):
    return text[pos] == quote and (quote == "'" or text[pos - 1] != "\\")


def strip_comment(line):
    """Drop a trailing comment outside quotes."""
    quote = None
    for pos, char in enumerate(line):
        if quote:
            if closes_quote(line, pos, quote):
                quote = None
        elif opens_quote(line, pos):
            quote = char
        elif char == "#" and (pos == 0 or line[pos - 1] in " \t"):
            return line[:pos].rstrip()
    return line.rstrip()


def flow_balance(text):
    depth, quote = 0, None
    for pos, char in enumerate(text):
        if quote:
            if closes_quote(text, pos, quote):
                quote = None
        elif opens_quote(text, pos):
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
    return depth


def split_key(text):
    """Split `key: value`; return (key, rest) or None when text is not a mapping entry."""
    if not text or text[0] in "[{&*!|>%@`":
        return None
    if text[0] in "'\"":
        key, pos = quoted(text, 0)
        rest = text[pos:].lstrip()
        if rest == ":" or rest.startswith(": "):
            return key, rest[1:].strip()
        return None
    match = re.search(r":(?: |$)", text)
    if not match:
        return None
    return scalar(text[:match.start()].rstrip()), text[match.end():].strip()


class SubsetReader:
    """Read the block and flow YAML used in Cerbos fixtures and test suites."""

    def __init__(self, text, source):
        self.lines = text.splitlines()
        self.source = source
        self.index = 0

    def fail(self, message):
        raise Unreadable(f"{self.source}:{self.index + 1}: {message} (install PyYAML to read it)")

    def peek(self):
        """Return (indent, content) of the next significant line, or None."""
        while self.index < len(self.lines):
            raw = self.lines[self.index]
            content = strip_comment(raw)
            if content.strip():
                indent = len(content) - len(content.lstrip(" "))
                if content[indent] == "\t":
                    self.fail("tab indentation")
                return indent, content.strip()
            self.index += 1
        return None

    def document(self):
        line = self.peek()
        if line and line[1] == "---":
            self.index += 1
            line = self.peek()
        if line is None:
            return None
        value = self.node(line[0])
        line = self.peek()
        if line and line[1] != "...":
            self.fail("expected one document")
        return value

    def node(self, indent):
        content = self.peek()[1]
        if content == "-" or content.startswith("- "):
            return self.sequence(indent)
        try:
            entry = split_key(content)
        except ValueError as error:
            self.fail(str(error))
        if entry:
            return self.mapping(indent)
        self.index += 1
        return self.inline(content)

    def mapping(self, indent):
        result = {}
        while (line := self.peek()) and line[0] == indent:
            content = line[1]
            if content == "-" or content.startswith("- "):
                break
            try:
                entry = split_key(content)
            except ValueError as error:
                self.fail(str(error))
            if entry is None:
                self.fail("expected `key: value`")
            key, rest = entry
            if key == "<<" or content.startswith("? "):
                self.fail("merge and complex keys are not supported")
            self.index += 1
            result[key] = self.value(rest, indent, in_mapping=True)
        if (line := self.peek()) and line[0] > indent:
            self.fail("unexpected indentation")
        return result

    def sequence(self, indent):
        result = []
        while (line := self.peek()) and line[0] == indent:
            content = line[1]
            if content != "-" and not content.startswith("- "):
                break
            rest = content[1:].lstrip()
            column = indent + len(content) - len(rest)
            nested = rest == "-" or rest.startswith("- ")
            try:
                entry = split_key(rest) if rest and not nested else None
            except ValueError as error:
                self.fail(str(error))
            if entry or nested:
                self.lines[self.index] = " " * column + rest
                result.append(self.mapping(column) if entry else self.sequence(column))
                continue
            self.index += 1
            result.append(self.value(rest, indent, in_mapping=False))
        return result

    def value(self, rest, indent, in_mapping):
        if rest == "":
            line = self.peek()
            if line and line[0] > indent:
                return self.node(line[0])
            if in_mapping and line and line[0] == indent and (line[1] == "-" or line[1].startswith("- ")):
                return self.sequence(indent)
            return None
        if rest[0] in "|>":
            return self.block_scalar(rest, indent)
        if rest[0] not in "[{'\"":
            while (line := self.peek()) and line[0] > indent:
                rest += " " + line[1]
                self.index += 1
        return self.inline(rest)

    def inline(self, text):
        if text[0] in "&*!%@`?":
            self.fail("anchors, aliases and tags are not supported")
        if text[0] in "[{":
            while flow_balance(text) > 0 and self.index < len(self.lines):
                text += " " + strip_comment(self.lines[self.index]).strip()
                self.index += 1
            try:
                value, pos = self.flow(text, 0)
            except (ValueError, IndexError) as error:
                self.fail(f"cannot read flow collection: {error}")
            if text[pos:].strip():
                self.fail("unexpected text after flow collection")
            return value
        if text[0] in "'\"":
            try:
                value, pos = quoted(text, 0)
            except ValueError as error:
                self.fail(str(error))
            if text[pos:].strip():
                self.fail("unexpected text after quoted string")
            return value
        return scalar(text)

    def flow(self, text, pos):
        pos = self.skip(text, pos)
        char = text[pos]
        if char == "[":
            items, pos = [], self.skip(text, pos + 1)
            while text[pos] != "]":
                item, pos = self.flow(text, pos)
                items.append(item)
                pos = self.separator(text, pos, "]")
            return items, pos + 1
        if char == "{":
            entries, pos = {}, self.skip(text, pos + 1)
            while text[pos] != "}":
                key, pos = self.flow(text, pos)
                pos = self.skip(text, pos)
                if text[pos] != ":":
                    raise ValueError("expected `:` in flow mapping")
                entries[key], pos = self.flow(text, pos + 1)
                pos = self.separator(text, pos, "}")
            return entries, pos + 1
        if char in "'\"":
            return quoted(text, pos)
        end = pos
        while end < len(text) and text[end] not in ",[]{}" and not (
            text[end] == ":" and (end + 1 == len(text) or text[end + 1] in " ,[]{}")
        ):
            end += 1
        return scalar(text[pos:end].strip()), end

    @staticmethod
    def skip(text, pos):
        while text[pos] == " ":
            pos += 1
        return pos

    def separator(self, text, pos, close):
        pos = self.skip(text, pos)
        if text[pos] == ",":
            return self.skip(text, pos + 1)
        if text[pos] != close:
            raise ValueError(f"expected `,` or `{close}`")
        return pos

    def block_scalar(self, header, indent):
        match = re.fullmatch(r"([|>])([-+]?)([1-9]?)([-+]?)", header)
        if not match:
            self.fail(f"unsupported block scalar header {header!r}")
        style, chomp = match.group(1), match.group(2) or match.group(4)
        lines = []
        while self.index < len(self.lines):
            raw = self.lines[self.index]
            if raw.strip() and len(raw) - len(raw.lstrip(" ")) <= indent:
                break
            lines.append(raw)
            self.index += 1
        width = int(match.group(3)) + indent if match.group(3) else min(
            (len(line) - len(line.lstrip(" ")) for line in lines if line.strip()), default=0
        )
        body = [line[width:] for line in lines]
        while body and not body[-1].strip():
            body.pop()
        trailing = len(lines) - len(body)
        if style == "|":
            text = "\n".join(body)
        else:
            text, previous = "", None
            for line in body:
                if previous is None:
                    text = line
                elif not line or line.startswith(" ") or not previous or previous.startswith(" "):
                    text += "\n" + line
                else:
                    text += " " + line
                previous = line
        if not body:
            return ""
        if chomp == "-":
            return text
        if chomp == "+":
            return text + "\n" * (trailing + 1)
        return text + "\n"


def read_yaml(path):
    text = path.read_text()
    if yaml:
        try:
            return yaml.load(text, Loader=_Loader)
        except yaml.YAMLError as error:
            raise Unreadable(f"{path}: {error}") from error
    return SubsetReader(text, path).document()


def load(path):
    if not path.is_file():
        return {}
    if path.suffix == ".json":
        try:
            return json.loads(path.read_text()) or {}
        except json.JSONDecodeError as error:
            raise Unreadable(f"{path}: {error}") from error
    return read_yaml(path) or {}


def scoped_policies(policies):
    """Return {(kind or None, scope, role or None)} for rules that exist only in a scope.

    A scoped resource policy contributes each role its rules name (None for "*"
    or derived roles),
    keyed by its resource kind. A scoped role policy contributes its role for
    every resource, so its kind is None. Also returns every scope with a policy.
    """
    scopes, all_scopes = set(), set()
    for path in sorted(policies.rglob("*")):
        if path.suffix not in {".yaml", ".yml", ".json"} or path.name.endswith(("_test.yaml", "_test.yml", "_test.json")):
            continue
        if "testdata" in path.parts or "_schemas" in path.relative_to(policies).parts:
            continue
        document = load(path)
        if not isinstance(document, dict):
            continue
        resource_policy = document.get("resourcePolicy") or {}
        role_policy = document.get("rolePolicy") or {}
        all_scopes.update(s for s in (resource_policy.get("scope"), role_policy.get("scope")) if s)
        if resource_policy.get("scope"):
            for rule in resource_policy.get("rules") or []:
                # Derived roles never appear in principal fixtures, so any role qualifies.
                for role in rule.get("roles") or ["*"]:
                    scopes.add((resource_policy.get("resource"), resource_policy["scope"], None if role == "*" else role))
        if role_policy.get("scope"):
            scopes.add((None, role_policy["scope"], role_policy.get("role")))
    return scopes, all_scopes


def fixtures(policies, suite_file, cache):
    """Resolve fixture keys for a suite: sibling testdata, then inline entries."""
    if suite_file in cache:
        return cache[suite_file]
    suite_path = policies / suite_file
    testdata = suite_path.parent / "testdata"
    suite = load(suite_path)
    resolved = {}
    for name in ("principals", "resources"):
        shared = {}
        for extension in ("yaml", "yml", "json"):
            shared.update(load(testdata / f"{name}.{extension}").get(name) or {})
        resolved[name] = {**shared, **(suite.get(name) or {})}
    cache[suite_file] = resolved
    return resolved


def flatten(principal, resource):
    fields = {
        "principal.id": principal.get("id"),
        "principal.roles": sorted(principal.get("roles") or []),
        "resource.kind": resource.get("kind"),
    }
    for side, value in (("principal", principal), ("resource", resource)):
        for key in ("scope", "policyVersion"):
            fields[f"{side}.{key}"] = value.get(key, ABSENT)
        for key, attr in (value.get("attr") or {}).items():
            fields[f"{side}.attr.{key}"] = attr
    return fields


def differences(left, right):
    keys = set(left) | set(right)
    return {
        key: (left.get(key, ABSENT), right.get(key, ABSENT))
        for key in sorted(keys)
        if left.get(key, ABSENT) != right.get(key, ABSENT)
    }


def executed(report):
    """Yield (suite file, test name, principal key, resource key, action, effect)."""
    for suite in report.get("suites", []):
        for case in suite.get("testCases", []):
            for principal in case.get("principals", []):
                for resource in principal.get("resources", []):
                    for action in resource.get("actions", []):
                        details = action.get("details", {})
                        if details.get("result") != "RESULT_PASSED":
                            continue
                        effect = details.get("success", {}).get("effect")
                        yield (
                            suite.get("file"),
                            case.get("name"),
                            principal.get("name"),
                            resource.get("name"),
                            action.get("name"),
                            effect,
                        )


def find(row, assertions):
    return [
        a
        for a in assertions
        if a[2] == row["principal"]
        and a[3] == row["resource"]
        and a[4] == row["action"]
        and a[5] == row["effect"]
        and row.get("suite") in (None, a[0])
        and row.get("test") in (None, a[1])
    ]


def load_plan(path):
    try:
        plan = json.loads(Path(path).read_text())
    except json.JSONDecodeError as error:
        raise Unreadable(f"{path}: the coverage plan must be JSON ({error})") from error
    if not isinstance(plan, dict):
        raise Unreadable(f"{path}: the coverage plan must be a JSON object with `rows`")
    return plan


def principal_id_matters(policies):
    """True when any policy reads the principal ID or targets a principal."""
    for path in policies.rglob("*"):
        if path.suffix not in {".yaml", ".yml", ".json"} or "testdata" in path.parts:
            continue
        if path.name.endswith(("_test.yaml", "_test.yml", "_test.json")):
            continue
        text = path.read_text(errors="replace")
        if re.search(r"\bP\.id\b|\bprincipal\.id\b|principalPolicy", text):
            return True
    return False


def audit(args):
    """Return (errors, passes) for the plan against the reports."""
    policies = Path(args.policies)
    passes = []
    plan = load_plan(args.plan)
    rows = plan.get("rows") or []
    if not rows:
        return ["plan has no rows"], passes
    by_id = {}
    errors = []
    for row in rows:
        missing = {"id", "principal", "resource", "action", "effect"} - set(row)
        if missing:
            errors.append(f"row {row!r} is missing {sorted(missing)}")
            continue
        if row["effect"] not in EFFECTS:
            errors.append(f"{row['id']}: effect must be EFFECT_ALLOW or EFFECT_DENY")
        if row["id"] in by_id:
            errors.append(f"{row['id']}: duplicate row id")
        change = [row["change"]] if isinstance(row.get("change"), str) else []
        for field in [*(row.get("facts") or {}), *change]:
            if not FIELD.fullmatch(field):
                errors.append(f"{row['id']}: unknown field path {field!r}; use {FIELDS}")
        by_id[row["id"]] = row
    if errors:
        return errors, passes

    reports = []
    for path in args.report:
        try:
            report = json.loads(Path(path).read_text())
        except json.JSONDecodeError as error:
            raise Unreadable(f"{path}: {error}") from error
        overall = report.get("summary", {}).get("overallResult")
        if overall != "RESULT_PASSED":
            errors.append(f"{path}: overall result is {overall}")
        reports.append((path, list(executed(report))))

    id_matters = principal_id_matters(policies)
    cache = {}
    requests = {}
    passed = set()
    for row in rows:
        for path, assertions in reports:
            matches = find(row, assertions)
            if not matches:
                errors.append(
                    f"FAIL {row['id']}: no passing {row['effect']} assertion for "
                    f"{row['principal']} / {row['resource']} / {row['action']} in {path}"
                )
                continue
            suite_file = matches[0][0]
            resolved = fixtures(policies, suite_file, cache)
            principal = resolved["principals"].get(row["principal"])
            resource = resolved["resources"].get(row["resource"])
            if principal is None or resource is None:
                errors.append(f"FAIL {row['id']}: fixture keys not found for {suite_file}")
                continue
            requests[row["id"]] = flatten(principal, resource)

    for row in rows:
        if row["id"] not in requests:
            continue
        request = requests[row["id"]]
        wrong = {
            path: request.get(path, ABSENT)
            for path, value in (row.get("facts") or {}).items()
            if request.get(path, ABSENT) != (ABSENT if value is None else value)
        }
        if wrong:
            detail = ", ".join(f"{k}={v!r} (planned {row['facts'][k]!r})" for k, v in wrong.items())
            errors.append(f"FAIL {row['id']}: fixture facts differ from the plan: {detail}")
            continue
        line = (
            f"{row['id']}: {request['resource.kind']} {row['action']} "
            f"{row['principal']} / {row['resource']} -> {row['effect']}"
        )
        control_id = row.get("control")
        if control_id is None:
            if "change" in row:
                errors.append(f"FAIL {line}; `change` needs a `control`")
            else:
                passes.append(f"PASS {line}")
                passed.add(row["id"])
            continue
        control = by_id.get(control_id)
        change = row.get("change")
        if control is None or control_id not in requests:
            errors.append(f"FAIL {line}; control {control_id!r} is not a passing row")
            continue
        if not isinstance(change, str):
            errors.append(f"FAIL {line}; `change` must name exactly one field")
            continue
        problems = []
        if control["effect"] == row["effect"]:
            problems.append(f"control {control_id} has the same effect")
        if control["action"] != row["action"]:
            problems.append(f"control {control_id} uses action {control['action']}")
        diff = differences(requests[control_id], request)
        diff.pop("resource.id", None)
        if not id_matters and change != "principal.id":
            # No policy reads the principal ID, so it cannot explain a decision.
            diff.pop("principal.id", None)
        if set(diff) != {change}:
            detail = ", ".join(f"{k}: {a!r} -> {b!r}" for k, a, b in
                               ((k, *v) for k, v in diff.items())) or "nothing"
            problems.append(f"expected only {change} to differ, found {detail}")
        if problems:
            errors.append(f"FAIL {line}; " + "; ".join(problems))
        else:
            before, after = diff[change]
            passes.append(f"PASS {line}; vs {control_id}: {change} {before!r} -> {after!r}")
            passed.add(row["id"])

    for path in plan.get("paths") or []:
        for prerequisite in path.get("requires") or []:
            isolated = [
                row["id"]
                for row in rows
                if row.get("path") == path.get("id")
                and row.get("prerequisite") == prerequisite
                and row.get("control")
                and row["id"] in passed
                and requests[row["id"]]["resource.kind"] == path.get("kind")
            ]
            label = f"path {path.get('id')} ({path.get('kind')}) prerequisite {prerequisite}"
            if isolated:
                passes.append(f"PASS {label}: {', '.join(isolated)}")
            else:
                errors.append(
                    f"FAIL {label}: no passing isolated row with a control; add a DENY row with this "
                    "`path` and `prerequisite`, a passing ALLOW `control`, and the one differing field as `change`"
                )

    exempt = {
        (item.get("scope"), item.get("role"))
        for item in plan.get("scopeExemptions") or []
        if item.get("reason")
    }
    scoped, scopes = scoped_policies(policies)
    root = lambda scope: scope.split(".")[0]
    required = {}
    for kind, scope, role in scoped:
        # A scoped rule also governs every descendant scope that has its own policy.
        for target in [scope, *sorted(s for s in scopes if s.startswith(scope + "."))]:
            # Compare against a sibling branch when one exists, so the pair also shows the
            # rule does not leak there; otherwise against the unscoped base.
            siblings = sorted(s for s in scopes if root(s) != root(target))
            required[(kind, target, role)] = (scope, siblings or [ABSENT])
    for (kind, target, role), (origin, others) in sorted(required.items(), key=lambda item: tuple(x or "" for x in item[0])):
        boundary = [
            row["id"]
            for row in rows
            if row["id"] in passed
            and row.get("change") == "resource.scope"
            and kind in (None, requests[row["id"]]["resource.kind"])
            and (role is None or role in requests[row["id"]]["principal.roles"])
            and {requests[row["id"]].get("resource.scope", ABSENT), requests[row["control"]].get("resource.scope", ABSENT)}
            in [{target, other} for other in others]
        ]
        versus = "the unscoped base" if others == [ABSENT] else " or ".join(f"`{other}`" for other in others)
        label = f"scope {target} ({kind or 'role policy'}{', role ' + role if role else ''}) vs {versus}"
        if boundary:
            passes.append(f"PASS {label}: {', '.join(boundary)}")
        elif (target, role) in exempt or (origin, role) in exempt:
            passes.append(f"NOTE {label}: exempted in the plan")
        else:
            inherited = f", inherited from `{origin}`," if origin != target else ""
            errors.append(
                f"FAIL {label}: no passing row shows the `{target}` policy chain{inherited} deciding differently; "
                f"add a row with `change: resource.scope` for a principal with that role whose control is a request "
                f"decided in `{target}`, moved to {versus}, with the opposite effect. If no request can differ because "
                "the rule only restates its parent, list it in `scopeExemptions` with a reason"
            )
    if any(role for _, _, role in scoped):
        union = [
            row["id"]
            for row in rows
            if row["id"] in passed
            and row["effect"] == "EFFECT_ALLOW"
            and row.get("change") == "principal.roles"
            and len(requests[row["id"]]["principal.roles"]) > 1
            and set(requests[row["control"]]["principal.roles"]) < set(requests[row["id"]]["principal.roles"])
        ]
        exemption = (plan.get("roleUnionExemption") or {}).get("reason")
        if union:
            passes.append(f"PASS role union: {', '.join(union)}")
        elif exemption:
            passes.append("NOTE role union: exempted in the plan")
        else:
            errors.append(
                "FAIL role union: scoped rules apply per role and roles combine, but no passing row shows it; add an "
                "ALLOW row for a principal holding two roles whose control, the same principal with one of those roles "
                "removed (`change: principal.roles`), is DENY. If no such request exists, set "
                "`roleUnionExemption: {\"reason\": ...}` in the plan"
            )
    return errors, passes


def compile_digest(name, output):
    """Summarise a `cerbos compile --output=json` result: compile errors and failing tests."""
    try:
        report = json.loads(output)
    except json.JSONDecodeError:
        return [f"COMPILE {name}: no JSON output: {output.strip()[:400]}"], False
    if "suites" not in report:
        lines = []
        for group in report.values():
            for entries in (group.values() if isinstance(group, dict) else [group]):
                for entry in entries if isinstance(entries, list) else [entries]:
                    if isinstance(entry, dict):
                        message = entry.get("error") or entry.get("description") or entry.get("message") or entry
                        lines.append(f"COMPILE {name}: {entry.get('file', '?')}: {message}")
        return lines or [f"COMPILE {name}: {output.strip()[:400]}"], False
    lines = []
    for suite in report["suites"]:
        for case in suite.get("testCases", []):
            for principal in case.get("principals", []):
                for resource in principal.get("resources", []):
                    for action in resource.get("actions", []):
                        details = action.get("details", {})
                        if details.get("result") == "RESULT_PASSED":
                            continue
                        failure = details.get("failure") or {}
                        why = (
                            f"expected {failure.get('expected')} got {failure.get('actual')}"
                            if failure else details.get("error") or details.get("result")
                        )
                        lines.append(
                            f"TEST {name}: {suite.get('file')} :: {case.get('name')} :: "
                            f"{principal.get('name')} / {resource.get('name')} / {action.get('name')}: {why}"
                        )
    return lines, True


def run_compiles(policies, plan):
    """Write normal.json and strict.json next to the plan; return (report paths, digest lines, compiled)."""
    paths, digest, compiled = [], [], True
    for name, flags in (("normal.json", []), ("strict.json", ["--strict-evaluation"])):
        path = Path(plan).resolve().parent / name
        try:
            result = subprocess.run(
                ["cerbos", "compile", "--output=json", *flags, policies],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
        except FileNotFoundError as error:
            raise Unreadable("`cerbos` is not on PATH; compile with Docker and pass --report instead") from error
        path.write_text(result.stdout)
        paths.append(str(path))
        lines, ok = compile_digest(name, result.stdout)
        digest += lines
        compiled = compiled and ok
    return paths, digest, compiled


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--policies", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--report", action="append", help="a saved `cerbos compile --output=json` report")
    parser.add_argument(
        "--run", action="store_true",
        help="run both compile passes, save normal.json and strict.json next to the plan, and audit them",
    )
    args = parser.parse_args()
    if args.run == bool(args.report):
        parser.error("pass either --run or at least one --report")
    try:
        if args.run:
            args.report, digest, compiled = run_compiles(args.policies, args.plan)
            for line in digest:
                print(line)
            if not compiled:
                print("coverage audit FAILED: fix compilation first")
                sys.exit(1)
        errors, passes = audit(args)
    except Unreadable as error:
        print(f"coverage audit could not run: {error}")
        sys.exit(2)
    for line in errors + passes:
        print(line)
    print(f"coverage audit {'FAILED' if errors else 'passed'}: {len(errors)} failing, {len(passes)} passing")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
