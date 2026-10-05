"""No role-name decisions remain in the application code.

Lenient by design: only flags role-name string literals used in a comparison,
a `match` case, or a literal list/tuple/set/dict (a role allowlist or a
role-to-permission table). Building the principal from `user["role"]` is fine.
Test files are ignored.
"""

import ast
from pathlib import Path

APP = Path("/workspace/app")
ROLES = {"admin", "manager", "accountant", "viewer"}


def is_role(node):
    return isinstance(node, ast.Constant) and node.value in ROLES


def findings(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        hit = None
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for operand in operands:
                if is_role(operand):
                    hit = operand.value
                elif isinstance(operand, (ast.List, ast.Tuple, ast.Set)):
                    hit = next((e.value for e in operand.elts if is_role(e)), None)
                if hit:
                    break
        elif isinstance(node, ast.MatchValue) and is_role(node.value):
            hit = node.value.value
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            hit = next((e.value for e in node.elts if is_role(e)), None)
        elif isinstance(node, ast.Dict):
            hit = next((k.value for k in node.keys if k is not None and is_role(k)), None)
        if hit:
            yield f"{path}:{node.lineno}: role {hit!r} used in application logic"


def main():
    problems = []
    files = [
        p
        for p in sorted(APP.rglob("*.py"))
        if not p.name.startswith("test_")
        and not p.name.endswith("_test.py")
        and "tests" not in p.relative_to(APP).parts
        and ".venv" not in p.parts
    ]
    if not files:
        raise SystemExit("No application code under /workspace/app")
    for path in files:
        try:
            problems.extend(findings(path))
        except SyntaxError as error:
            problems.append(f"{path}: does not parse: {error}")
    for problem in problems:
        print(problem)
    if problems:
        raise SystemExit("Role checks are still decided in application code")
    print(f"PASS: no role-name decisions in {len(files)} application files")


if __name__ == "__main__":
    main()
