"""Check every skill under plugins/cerbos-skills/skills/ against the repository's structural rules.

Run from anywhere with:

    uv run --no-project --with PyYAML==6.0.2 python scripts/validate_skills.py [--base REF] [--links]

Checks:

1. SKILL.md frontmatter uses only Agent Skills fields, `name` matches its
   directory, `description` is present and within limits, and
   `metadata.version` is set.
2. SKILL.md stays within MAX_SKILL_LINES.
3. Every file in a skill is reachable from its SKILL.md, directly or through a
   file SKILL.md references, so no reference silently drops out of use.
4. Local Markdown links and their heading anchors resolve.
5. Container images in skill content use a pinned tag, not `latest`.
6. With --base, every skill whose files changed since REF has a higher
   `metadata.version` than it had at REF.
7. The plugin and marketplace manifests for each agent (Claude Code, Codex,
   Cursor, Copilot, Gemini) parse as JSON and agree on plugin name and version,
   and every marketplace installs the plugin from PLUGIN_DIR.
8. The names and descriptions of all skills together fit the skills-list
   budget hosts enforce; a description over DESCRIPTION_BUDGET is a warning.
9. With --links, every external URL in skill prose resolves. Off by default so
   the check runs offline; CI turns it on.

Exits 1 and names each offending file when any check fails. Warnings are
printed but do not fail the run.
"""

import argparse
import concurrent.futures
import itertools
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = "cerbos-skills"
PLUGIN_DIR = f"plugins/{PLUGIN}"
SKILLS = ROOT / PLUGIN_DIR / "skills"
DOCS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / PLUGIN_DIR / "README.md",
    ROOT / "evals" / "README.md",
]
PLUGIN_MANIFESTS = [
    f"{PLUGIN_DIR}/.claude-plugin/plugin.json",
    f"{PLUGIN_DIR}/.codex-plugin/plugin.json",
    f"{PLUGIN_DIR}/.cursor-plugin/plugin.json",
    "gemini-extension.json",
]
MARKETPLACES = [
    ".claude-plugin/marketplace.json",
    ".github/plugin/marketplace.json",
    ".cursor-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
]
MAX_SKILL_LINES = 500
# A description loads on every turn; past this it is doing the body's job.
DESCRIPTION_BUDGET = 600
# Hosts cap the skills list they show a model at 2% of the context window, or
# 8,000 characters when that is unknown, and truncate descriptions past it.
SKILLS_LIST_BUDGET = 8000
FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
BRACES = re.compile(r"[\w./-]*\{[^{}\s]+\}[\w./-]*")
URL = re.compile(r"https?://[^\s<>\"'\)\]`]+")
INLINE_CODE = re.compile(r"`[^`\n]+`")
# Placeholder hosts and unsubstituted values illustrate a shape; nobody opens them.
PLACEHOLDERS = ("localhost", "127.0.0.1", "0.0.0.0", "example.com", "example.org",
                "example.net", "my-bucket", "your-org", "...", "<", "YOUR_", "{", "$")
LATEST = re.compile(r"(?<![\w./-])(?:[\w.-]+/)+[\w.-]+:latest\b")


def frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return None
    return yaml.safe_load(match.group(1)) or {}


def version_key(value):
    return tuple(int(part) for part in str(value).split("."))


def check_frontmatter(skill, errors, warnings):
    path = skill / "SKILL.md"
    meta = frontmatter(path)
    if meta is None:
        errors.append(f"{rel(path)}: missing YAML frontmatter")
        return
    for key in sorted(set(meta) - FIELDS):
        errors.append(f"{rel(path)}: unsupported frontmatter field '{key}' (move it under metadata)")
    name = meta.get("name")
    if name != skill.name or not NAME.match(str(name)) or len(str(name)) > 64:
        errors.append(f"{rel(path)}: name '{name}' must equal the directory name '{skill.name}' in lowercase-hyphen form")
    description = str(meta.get("description") or "").strip()
    if not description or len(description) > 1024:
        errors.append(f"{rel(path)}: description must be 1-1024 characters, found {len(description)}")
    elif len(description) > DESCRIPTION_BUDGET:
        warnings.append(f"{rel(path)}: description is {len(description)} characters (budget {DESCRIPTION_BUDGET}); trim it, it loads every turn")
    if len(str(meta.get("compatibility") or "")) > 500:
        errors.append(f"{rel(path)}: compatibility exceeds 500 characters")
    version = (meta.get("metadata") or {}).get("version")
    try:
        version_key(version)
    except ValueError:
        errors.append(f"{rel(path)}: metadata.version must be a dotted number such as \"1.0\", found {version!r}")
    lines = path.read_text().count("\n")
    if lines > MAX_SKILL_LINES:
        errors.append(f"{rel(path)}: {lines} lines exceeds {MAX_SKILL_LINES}; move reference material into references/")


def expand(token):
    """Expand shell-style braces: a-{b,c}.md -> a-b.md, a-c.md."""
    parts = re.split(r"\{([^{}]+)\}", token)
    options = [[p] if i % 2 == 0 else p.split(",") for i, p in enumerate(parts)]
    return ["".join(choice) for choice in itertools.product(*options)]


def mentions(text):
    """The text plus every brace-expanded path it names."""
    return text + "\n" + "\n".join(
        path for token in BRACES.findall(text) for path in expand(token)
    )


def names(text, target, source):
    """Whether text refers to target, by skill-relative or source-relative path."""
    for candidate in {target.as_posix(), Path(os.path.relpath(target, source.parent)).as_posix()}:
        if re.search(rf"(?<![\w./-]){re.escape(candidate)}(?![\w-])", text):
            return True
    return False


def check_reachable(skill, errors):
    files = sorted(
        p.relative_to(skill) for p in skill.rglob("*")
        if p.is_file() and p.name != "SKILL.md" and "__pycache__" not in p.parts
    )
    reached, frontier = set(), [Path("SKILL.md")]
    while frontier:
        source = frontier.pop()
        text = mentions((skill / source).read_text(errors="replace"))
        for target in files:
            if target not in reached and names(text, target, source):
                reached.add(target)
                frontier.append(target)
    for target in files:
        if target not in reached:
            errors.append(f"{rel(skill / target)}: not referenced from SKILL.md or any file it references")


def slug(heading):
    text = re.sub(r"[`*]|\[([^\]]*)\]\([^)]*\)", r"\1", heading).strip().lower()
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", text))


def anchors(path):
    seen, result = {}, set()
    for heading in HEADING.findall(FENCE.sub("", path.read_text())):
        base = slug(heading)
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


def check_links(path, errors):
    for target in LINK.findall(FENCE.sub("", path.read_text())):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target):
            continue
        file_part, _, anchor = target.partition("#")
        resolved = (path.parent / file_part).resolve() if file_part else path
        if not resolved.exists():
            errors.append(f"{rel(path)}: link target '{target}' does not exist")
        elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
            errors.append(f"{rel(path)}: link '{target}' names a heading that does not exist")


def check_image_tags(skill, errors):
    for path in sorted(p for p in skill.rglob("*") if p.is_file() and p.suffix in {".md", ".yaml", ".yml", ".sh", ".py"}):
        for image in sorted(set(LATEST.findall(path.read_text(errors="replace")))):
            errors.append(f"{rel(path)}: image '{image}' uses the latest tag; pin the release the skill targets")


def check_skills_list(skills, errors):
    total = 0
    for skill in skills:
        meta = frontmatter(skill / "SKILL.md") or {}
        total += len(skill.name) + len(str(meta.get("description") or "").strip())
    if total > SKILLS_LIST_BUDGET:
        errors.append(f"skill names and descriptions total {total} characters, over the {SKILLS_LIST_BUDGET} skills-list budget")
    return total


def prose_urls(path):
    prose = INLINE_CODE.sub("", FENCE.sub("", path.read_text()))
    return {
        url.rstrip(".,;:") for url in URL.findall(prose)
        if not any(marker in url for marker in PLACEHOLDERS)
    }


def fetch(url):
    # A connection failure is often transient, so retry it with backoff; a
    # definite HTTP status is taken at face value.
    last = "unknown"
    for attempt in range(3):
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "cerbos-skills-validate"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return 200 if error.code in (403, 405) else error.code  # HEAD refused; the page is fine
        except Exception as error:  # noqa: BLE001 - transient; retry
            last = type(error).__name__
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    return last


def check_urls(urls, errors):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for url, status in zip(sorted(urls), pool.map(fetch, sorted(urls))):
            if status != 200:
                errors.append(f"{url}: resolves to {status}")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def check_version_bump(skill, base, errors):
    changed = git("diff", "--name-only", base, "--", rel(skill))
    if changed.returncode:
        errors.append(f"cannot diff against base '{base}': {changed.stderr.strip()}")
        return
    if not changed.stdout.strip():
        return
    previous = git("show", f"{base}:{rel(skill / 'SKILL.md')}")
    if previous.returncode:
        return  # New skill: no earlier version to exceed.
    match = re.search(r'^\s+version:\s*"?([\d.]+)"?\s*$', previous.stdout, re.MULTILINE)
    current = (frontmatter(skill / "SKILL.md") or {}).get("metadata", {}).get("version")
    try:
        if match and version_key(current) <= version_key(match.group(1)):
            errors.append(
                f"{rel(skill / 'SKILL.md')}: files changed since {base} but metadata.version "
                f"is {current}, not above {match.group(1)}; bump the minor version for new "
                "guidance or the major version for a change to when the skill applies"
            )
    except ValueError:
        pass  # Reported by check_frontmatter.


def check_manifests(errors):
    versions = {}

    def load(name):
        try:
            return json.loads((ROOT / name).read_text())
        except FileNotFoundError:
            errors.append(f"{name}: missing")
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: invalid JSON: {exc}")
        return None

    for name in PLUGIN_MANIFESTS:
        manifest = load(name)
        if manifest is None:
            continue
        if manifest.get("name") != PLUGIN:
            errors.append(f"{name}: name must be '{PLUGIN}'")
        versions[name] = manifest.get("version")
    for name in MARKETPLACES:
        marketplace = load(name)
        if marketplace is None:
            continue
        entries = [p for p in marketplace.get("plugins", []) if p.get("name") == PLUGIN]
        if not entries:
            errors.append(f"{name}: no '{PLUGIN}' plugin entry")
        for entry in entries:
            source = entry.get("source")
            if isinstance(source, dict):
                source = source.get("path")
            if Path(str(source)) != Path(PLUGIN_DIR):
                errors.append(f"{name}: '{PLUGIN}' source must be './{PLUGIN_DIR}', found {source!r}")
            if "version" in entry:
                versions[name] = entry["version"]
    if len(set(versions.values())) > 1:
        listed = ", ".join(f"{name}={version}" for name, version in versions.items())
        errors.append(f"plugin versions disagree; set one version everywhere: {listed}")


def rel(path):
    return path.relative_to(ROOT).as_posix()


def validate(base=None, links=False, warnings=None):
    errors = []
    warnings = [] if warnings is None else warnings
    urls = set()
    skills = sorted(p.parent for p in SKILLS.glob("*/SKILL.md"))
    if not skills:
        errors.append(f"no skills found under {rel(SKILLS)}")
    for skill in skills:
        check_frontmatter(skill, errors, warnings)
        check_reachable(skill, errors)
        check_image_tags(skill, errors)
        for path in sorted(skill.rglob("*.md")):
            check_links(path, errors)
            urls |= prose_urls(path)
        if base:
            check_version_bump(skill, base, errors)
    for path in DOCS:
        if path.exists():
            check_links(path, errors)
    check_manifests(errors)
    check_skills_list(skills, errors)
    if links:
        check_urls(urls, errors)
    return skills, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", help="git ref to compare skill versions against, e.g. the PR merge base")
    parser.add_argument("--links", action="store_true", help="also resolve every external URL in skill prose")
    args = parser.parse_args()
    warnings = []
    skills, errors = validate(args.base, args.links, warnings)
    for warning in warnings:
        print(f"WARN  {warning}", file=sys.stderr)
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    if errors:
        sys.exit(1)
    print(f"{len(skills)} skills valid")


if __name__ == "__main__":
    main()
