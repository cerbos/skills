"""Generate the Synapse smoke tasks under evals/tasks/ from the sources in this directory.

Run from anywhere:

    python3 evals/synapse/generate.py          # write evals/tasks/cerbos-synapse-*
    python3 evals/synapse/generate.py --check  # exit 1 if the tasks differ from their sources

Each generated task is self-contained, as Harbor requires. Edit the sources here,
never the generated task folders:

- common/     verifier, seeded policy and prepare-image.sh shared by every task
- kinds/      decision cases per extension kind (proxy, route, envoy)
- runtimes/   files copied into the image build context per runtime
- solutions/  reference solution per task, named <kind>-<runtime>
- this file   the task matrix, instructions, Dockerfiles, task.toml and READMEs
"""

import argparse
import filecmp
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent / "tasks"
PREFIX = "cerbos-synapse-"
SYNAPSE_VERSION = "0.10.2"

MATRIX = [
    ("proxy", "starlark"),
    ("proxy", "wasm-go"),
    ("proxy", "wasm-js"),
    ("proxy", "wasm-python"),
    ("route", "starlark"),
    ("route", "wasm-go"),
    ("route", "wasm-js"),
    ("route", "wasm-python"),
    ("envoy", "starlark"),
]

RUNTIME_NAMES = {
    "starlark": "Starlark",
    "wasm-go": "Go WASM",
    "wasm-js": "JavaScript/TypeScript WASM",
    "wasm-python": "Python WASM",
}

KIND_NAMES = {
    "proxy": "proxy extension",
    "route": "route extension",
    "envoy": "Envoy ext_authz extension",
}

# --- Instructions -----------------------------------------------------------

DIRECTORY = """| Principal ID | Department |
| --- | --- |
| `alice` | `engineering` |
| `bob` | `sales` |"""

DOCUMENTS = """| Document ID | Department | Tenant |
| --- | --- | --- |
| `eng-acme` | `engineering` | `acme` |
| `sales-acme` | `sales` | `acme` |
| `eng-globex` | `engineering` | `globex` |"""

POLICY_NOTE = """The policy in `/workspace/policies` grants `view` on a `document` to the `employee`
role only when the principal's `department` and `tenant` attributes match the
document's. Leave the policy unchanged."""


def extension_phrase(kind, runtime):
    what = {"proxy": "proxy extension", "route": "route extension",
            "envoy": "Envoy external authorization extension"}[kind]
    return {
        "starlark": f"a Starlark {what} under `/workspace/extensions/`",
        "wasm-go": f"a WebAssembly {what} in Go, as one Go module under `/workspace/extensions/`",
        "wasm-js": f"a WebAssembly {what} in TypeScript or JavaScript, as one npm project under `/workspace/extensions/`",
        "wasm-python": f"a WebAssembly {what} in Python under `/workspace/extensions/`",
    }[runtime]


def artifact_phrase(runtime):
    if runtime == "starlark":
        return "the extension"
    return "the built `.wasm`"


def build_note(runtime):
    return "" if runtime == "starlark" else " Build the module yourself and leave the `.wasm` on disk."


ENVIRONMENT = {
    "starlark": "",
    "wasm-go": (
        " Go 1.27.1 is installed, and the Go module cache already holds"
        " `github.com/extism/go-pdk` v1.1.3 and the `tidwall/gjson` and `tidwall/sjson` modules."
    ),
    "wasm-js": (
        " Node.js 24, `extism-js` and binaryen are installed, and the npm cache already"
        " holds `@extism/js-pdk` 1.1.1, `esbuild` 0.28.2 and `typescript` 7.0.2."
    ),
    "wasm-python": (
        " `extism-py` 0.1.5, `wasm-tools` and binaryen (`wasm-merge`) are installed as"
        " native executables; run build steps directly rather than through Docker."
    ),
}


def instruction(kind, runtime):
    extension, artifact = extension_phrase(kind, runtime), artifact_phrase(runtime)
    if kind == "proxy":
        body = f"""Use the installed `cerbos-synapse-extension` skill to add principal enrichment to
Cerbos Synapse in `/workspace`.

Applications call Synapse's CheckResources API with a principal ID, the `employee`
role and a `tenant` attribute, but without the principal's department. {POLICY_NOTE}

Write {extension} that sets the principal's `department` attribute from this
directory before the PDP evaluates CheckResources requests:

{DIRECTORY}

The directory is authoritative: its department replaces any `department` the
caller sends, and principals not in the directory end up with no `department`
attribute at all, even if the caller sent one, so they are denied. Keep every
other attribute the caller sends, including `tenant`.

Write the Synapse configuration to `/workspace/config.yaml`: an in-process PDP that
reads `/workspace/policies` from disk, with {artifact} loaded as a proxy
extension.{build_note(runtime)} Add a Synapse test suite under `/workspace/extensions/`
that shows an enriched principal is allowed and a principal from another department
is denied, and make sure it passes."""
    elif kind == "route":
        body = f"""Use the installed `cerbos-synapse-extension` skill to add a document access endpoint
to Cerbos Synapse in `/workspace`.

{POLICY_NOTE}

Write {extension} that serves `GET /ext/documents?id=<document id>`. Callers
send their principal ID in the `X-User-Id` header and their tenant in the
`X-Tenant` header. For each request, ask the PDP whether the caller, as an
`employee` with that tenant and the department from this directory, may `view`
the document:

{DIRECTORY}

The documents are:

{DOCUMENTS}

Callers not in the directory have no department, so they are denied. Respond with
HTTP 200 and the JSON body `{{"allowed": true}}` when the PDP allows, HTTP 403 and
`{{"allowed": false}}` when it denies, and HTTP 404 for an unknown document ID.

Write the Synapse configuration to `/workspace/config.yaml`: an in-process PDP that
reads `/workspace/policies` from disk, with {artifact} loaded as a route
extension.{build_note(runtime)} Add a Synapse test suite under `/workspace/extensions/`
that shows an allowed request, a denied request and an unknown document, and make
sure it passes."""
    else:
        body = f"""Use the installed `cerbos-synapse-extension` skill to put Cerbos Synapse in front
of a document service as an Envoy external authorization server, in `/workspace`.

{POLICY_NOTE}

Envoy sends Synapse an ext_authz check for each `GET /documents/<document id>`
request, with the caller's principal ID in the `x-user-id` header and tenant in
the `x-tenant` header. Write {extension} that asks the PDP whether the caller,
as an `employee` with that tenant and the department from this directory, may
`view` the document:

{DIRECTORY}

The documents are:

{DOCUMENTS}

Callers not in the directory have no department, so they are denied. Allow the
request with an OK status (code 0) when the PDP allows. Deny it with
PERMISSION_DENIED (code 7) and an HTTP 403 denied response when the PDP denies or
the document is unknown.

Write the Synapse configuration to `/workspace/config.yaml`: an in-process PDP that
reads `/workspace/policies` from disk, with {artifact} loaded as Synapse's Envoy
external authorization extension.{build_note(runtime)} Add a Synapse test suite under
`/workspace/extensions/` that shows an allowed check, a denied check and an unknown
document, and make sure it passes."""
    closing = (
        f"These requirements are confirmed; proceed with implementation. Synapse {SYNAPSE_VERSION}"
        " is installed as the native `synapse` executable, so no container image, registry"
        f" login or distribution repository is needed.{ENVIRONMENT[runtime]} Docker is"
        " unavailable inside this environment. Write every file to disk before responding."
    )
    return reflow(body + "\n\n" + closing) + "\n"


def reflow(text):
    """Wrap every paragraph except tables."""
    paragraphs = text.split("\n\n")
    return "\n\n".join(p if p.startswith("|") else wrap(p) for p in paragraphs)


def wrap(text, width=84):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    return "\n".join(lines + [line])


# --- Dockerfiles ------------------------------------------------------------

PYTHON_IMAGE = "python:3.12-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9"
GO_IMAGE = "golang:1.27.1-bookworm@sha256:69a7b9788769bec032d238959b61854e9ae87f57be9029ec04e9885fabf99195"
NODE_IMAGE = "node:24-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6"

RUNTIME_STAGES = {
    "wasm-go": f"# golang:1.27.1-bookworm\nFROM {GO_IMAGE} AS go\n",
    "wasm-js": f"# node:24-bookworm-slim\nFROM {NODE_IMAGE} AS node\n",
}

RUNTIME_LAYERS = {
    "starlark": "",
    "wasm-go": """
COPY --from=go /usr/local/go /usr/local/go
ENV PATH=/usr/local/go/bin:/root/go/bin:$PATH GOTOOLCHAIN=local
# Cache the Extism Go PDK, the JSON helpers and the wasip1 standard library so
# extensions build without network access.
COPY go-warm/ /tmp/go-warm/
RUN cd /tmp/go-warm && GOOS=wasip1 GOARCH=wasm go build -buildmode=c-shared -o /dev/null . \\
    && rm -rf /tmp/go-warm
""",
    "wasm-js": """
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \\
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \\
    && node --version && npm --version
# extism-js compiles bundled JavaScript to WASM and needs binaryen.
RUN set -eux; cd /tmp; \\
    case "$TARGETARCH" in \\
      amd64) arch=x86_64; js_sha=63b72da2f5e88655522dc21477de549f238a2f40546a69ce4e0fce7e78654035; bin_sha=2dc9c7813f5375db93d96ead4b78222fcc3e2677bbb832297af4797782a37489 ;; \\
      arm64) arch=aarch64; js_sha=025f4050b199d68413c159bde1187271ae270021a9f7171e7beb509922821f2a; bin_sha=89c07ea56faf38d0fbecf36ca8ec0721756716185f265b568e133d427f299bf8 ;; \\
      *) echo "unsupported architecture $TARGETARCH"; exit 1 ;; \\
    esac; \\
    curl -fsSLo extism-js.gz "https://github.com/extism/js-pdk/releases/download/v1.7.0/extism-js-$arch-linux-v1.7.0.gz"; \\
    echo "$js_sha  extism-js.gz" | sha256sum -c -; \\
    gunzip -c extism-js.gz > /usr/local/bin/extism-js && chmod +x /usr/local/bin/extism-js; \\
    curl -fsSLo binaryen.tgz "https://github.com/WebAssembly/binaryen/releases/download/version_133/binaryen-version_133-$arch-linux.tar.gz"; \\
    echo "$bin_sha  binaryen.tgz" | sha256sum -c -; \\
    tar xzf binaryen.tgz --strip-components=1 -C /usr/local; \\
    rm -f extism-js.gz binaryen.tgz; \\
    extism-js --version && wasm-merge --version
# Cache the packages an Extism JS extension typically uses.
COPY npm-warm/ /tmp/npm-warm/
RUN cd /tmp/npm-warm && npm install --no-audit --no-fund && rm -rf /tmp/npm-warm
""",
    "wasm-python": """
# extism-py ships for x86_64 Linux only (glibc 2.39+), hence the amd64 image.
RUN set -eux; cd /tmp; \\
    curl -fsSLo extism-py.tgz https://github.com/extism/python-pdk/releases/download/v0.1.5/extism-py-x86_64-linux-v0.1.5.tar.gz; \\
    echo "24fa8a4a2f2fe25e3a95a4dc1dbd10a4c30e97697102fec45c59bfc743b2d9d4  extism-py.tgz" | sha256sum -c -; \\
    tar xzf extism-py.tgz --strip-components=1 -C /usr/local; \\
    curl -fsSLo binaryen.tgz https://github.com/WebAssembly/binaryen/releases/download/version_133/binaryen-version_133-x86_64-linux.tar.gz; \\
    echo "2dc9c7813f5375db93d96ead4b78222fcc3e2677bbb832297af4797782a37489  binaryen.tgz" | sha256sum -c -; \\
    tar xzf binaryen.tgz --strip-components=1 -C /usr/local; \\
    curl -fsSLo wasm-tools.tgz https://github.com/bytecodealliance/wasm-tools/releases/download/v1.259.0/wasm-tools-1.259.0-x86_64-linux.tar.gz; \\
    echo "3e9b374b4c7715b771b69bf0d65a337990ed4546ec5e97e01c0ff587dfc52160  wasm-tools.tgz" | sha256sum -c -; \\
    tar xzf wasm-tools.tgz --strip-components=1 -C /usr/local/bin; \\
    rm -f extism-py.tgz binaryen.tgz wasm-tools.tgz; \\
    extism-py --version && wasm-merge --version && wasm-tools --version
""",
}


def dockerfile(runtime):
    amd64 = runtime == "wasm-python"
    platform = "--platform=linux/amd64 " if amd64 else ""
    synapse_tag = f"{SYNAPSE_VERSION}-amd64" if amd64 else SYNAPSE_VERSION
    arch_arg = "ARG TARGETARCH\n" if runtime == "wasm-js" else ""
    return f"""# Generated by evals/synapse/generate.py; edit the sources there.
# Licensed image, tagged locally by ../prepare-image.sh; the localhost/ prefix never resolves to a public registry.
FROM {platform}localhost/cerbos-synapse:{synapse_tag} AS synapse
{RUNTIME_STAGES.get(runtime, "")}
# python:3.12-slim-trixie
FROM {platform}{PYTHON_IMAGE}
{arch_arg}
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ca-certificates curl file git \\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir PyYAML==6.0.2

COPY --from=synapse /synapse /usr/local/bin/synapse
RUN synapse --version | grep -qx {SYNAPSE_VERSION}
ENV CERBOS_NO_TELEMETRY=1
{RUNTIME_LAYERS[runtime]}
WORKDIR /workspace
COPY policies/ /workspace/policies/
""".replace("\n\n\n", "\n\n")


# --- task.toml and README ---------------------------------------------------

def task_toml(kind, runtime, name):
    description = (f"Smoke test: build, wire and test a {RUNTIME_NAMES[runtime]} "
                   f"{KIND_NAMES[kind]} in Cerbos Synapse.")
    keywords = ["cerbos", "synapse", "authorization", "custom-verifier", kind, runtime]
    tags = ["synapse", kind, runtime, "smoke"]
    # Python builds run emulated on arm64 hosts; allow them more time.
    agent_timeout, verifier_timeout = (900, 600) if runtime == "wasm-python" else (600, 300)
    return f"""# Generated by evals/synapse/generate.py; edit the sources there.
schema_version = "1.3"
artifacts = [{{ source = "/workspace", destination = "workspace", exclude = [".agents", ".codex", ".claude", ".git", ".cache", ".pytest_cache", ".ruff_cache", "__pycache__", "*.pyc", "node_modules", ".venv"] }}]

[task]
name = "cerbos/{name}"
version = "1.0.0"
description = "{description}"
keywords = {json.dumps(keywords)}

[metadata]
difficulty = "easy"
category = "programming"
tags = {json.dumps(tags)}
name = "{name}"
description = "{description}"

[agent]
timeout_sec = {agent_timeout}

[verifier]
timeout_sec = {verifier_timeout}

[environment]
build_timeout_sec = 1800
cpus = 2
memory_mb = 4096
storage_mb = 8192
"""


DECISIONS = {
    "proxy": ("Eight CheckResources requests, sent over HTTP to a server started from the agent's"
              " config, return the expected decision: enrichment for both directory principals, a"
              " department mismatch, tenant preservation both ways, an unknown principal, an unknown"
              " principal claiming a department, and the directory overriding a false claim."),
    "route": ("Seven `GET /ext/documents` requests to a server started from the agent's config"
              " return the expected status and `allowed` body: both directory principals on their own"
              " documents, a department mismatch, a tenant mismatch and match, an unknown caller and an"
              " unknown document."),
    "envoy": ("Seven Envoy checks, sent through a verifier-owned `synapse test` suite that loads the"
              " agent's config (ext_authz is gRPC), return code 0 or code 7 with an HTTP 403 denied"
              " response for the same cases as the route task."),
}


def readme(kind, runtime, name):
    rows = [
        "| `files` | `config.yaml`, extension source and a `*_test.star` suite exist; the config loads an"
        f" existing {'`.star`' if runtime == 'starlark' else '`.wasm`'} {kind} extension"
        f"{'' if runtime == 'starlark' else ' built after its last source change'};"
        " the seeded policy is unchanged. |",
    ]
    if runtime == "wasm-go":
        rows.append("| `build` | The single Go module under `/workspace/extensions` builds with"
                    " `GOOS=wasip1 GOARCH=wasm go build -buildmode=c-shared`. |")
    rows += [
        "| `server_starts` | `synapse server` starts from the agent's `config.yaml` and"
        " `/_cerbos/ready` returns 200. |",
        "| `generated_tests` | `synapse test` passes every suite under `/workspace/extensions`,"
        " with at least two passing cases. |",
        f"| `decisions` | {DECISIONS[kind]} |",
    ]
    image_note = ""
    if runtime == "wasm-python":
        image_note = (" `extism-py` ships for x86_64 Linux only, so this image is linux/amd64 and runs"
                      " emulated on arm64 hosts; allow extra time.")
    siblings = ", ".join(f"[`{PREFIX}{k}-{r}`](../{PREFIX}{k}-{r}/README.md)"
                         for k, r in MATRIX if (k, r) != (kind, runtime))
    return f"""# {name}

<!-- Generated by evals/synapse/generate.py; edit the sources there. -->

A smoke test for the `cerbos-synapse-extension` skill: write a {RUNTIME_NAMES[runtime]}
{KIND_NAMES[kind]}, wire it into Synapse {SYNAPSE_VERSION} and prove it with a Synapse
test suite. The [instruction](instruction.md) gives the full request. Every task in the
matrix shares one seeded policy, principal directory and verifier; see
[`evals/synapse`](../../synapse/generate.py) for the sources.

## Environment

The image runs the native `synapse` binary on Python 3.12 (Debian Trixie) with the
{RUNTIME_NAMES[runtime]} toolchain; pinned versions are in `environment/Dockerfile`.{image_note}
Synapse is licensed, so the repository never names its distribution repository.
Before the first run, log in to the repository issued with your licence and tag the
image locally; one run covers every Synapse task:

```bash
export CERBOS_DISTRIBUTION_REPO=<repository URL issued with your licence>
docker login "$CERBOS_DISTRIBUTION_REPO"
evals/tasks/{name}/prepare-image.sh
```

## Verification

| Stage | Requirement |
| --- | --- |
{chr(10).join(rows)}

Every stage must pass for reward 1. Evidence is kept in `/logs/verifier`: one log per
stage, the server log, and the requests and results of the decision stage.

## Running

From the repository root, with Docker running and `prepare-image.sh` run once:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/{name} -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/{name} -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/{name} \\
  --skill ./skills/cerbos-synapse-extension -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

Oracle scores 1 and nop scores 0. Other Synapse tasks: {siblings}.
"""


# --- Assembly ---------------------------------------------------------------

def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("node_modules", "dist", "__pycache__", "*.wasm"))


def build_task(kind, runtime, root):
    name = f"{PREFIX}{kind}-{runtime}"
    task = root / name
    solution = HERE / "solutions" / f"{kind}-{runtime}"
    if not solution.is_dir():
        sys.exit(f"missing reference solution {solution}")
    (task / "environment").mkdir(parents=True)
    (task / "task.toml").write_text(task_toml(kind, runtime, name))
    (task / "instruction.md").write_text(instruction(kind, runtime))
    (task / "README.md").write_text(readme(kind, runtime, name))
    (task / "environment" / "Dockerfile").write_text(dockerfile(runtime))
    copy_tree(HERE / "common" / "environment", task / "environment")
    runtime_dir = HERE / "runtimes" / runtime
    if runtime_dir.is_dir():
        copy_tree(runtime_dir, task / "environment")
    shutil.copy2(HERE / "common" / "prepare-image.sh", task / "prepare-image.sh")
    copy_tree(HERE / "common" / "tests", task / "tests")
    shutil.copy2(HERE / "kinds" / kind / "tests" / "cases.json", task / "tests" / "cases.json")
    (task / "tests" / "task.json").write_text(json.dumps({"kind": kind, "runtime": runtime}) + "\n")
    copy_tree(solution, task / "solution")


def build_all(root):
    for kind, runtime in MATRIX:
        build_task(kind, runtime, root)


def differences(expected_root, actual_root):
    problems = []
    expected = {p.name for p in expected_root.iterdir()}
    actual = {p.name for p in actual_root.glob(f"{PREFIX}*")}
    problems += [f"missing task {n}" for n in sorted(expected - actual)]
    problems += [f"stale task {n} (not in the matrix)" for n in sorted(actual - expected)]

    def walk(cmp, prefix):
        problems.extend(f"{prefix}{n}: differs" for n in cmp.diff_files)
        problems.extend(f"{prefix}{n}: missing" for n in cmp.left_only)
        problems.extend(f"{prefix}{n}: unexpected" for n in cmp.right_only)
        for sub, child in cmp.subdirs.items():
            walk(child, f"{prefix}{sub}/")

    for name in sorted(expected & actual):
        walk(filecmp.dircmp(expected_root / name, actual_root / name,
                            ignore=["node_modules", "dist", "__pycache__"]), f"{name}/")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="verify generated tasks match their sources")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_all(root)
        if args.check:
            problems = differences(root, TASKS)
            for problem in problems:
                print(f"ERROR {problem}", file=sys.stderr)
            if problems:
                sys.exit("Generated Synapse tasks are out of date: run python3 evals/synapse/generate.py")
            print(f"{len(MATRIX)} Synapse tasks match their sources")
            return
        for old in TASKS.glob(f"{PREFIX}*"):
            shutil.rmtree(old)
        for task in sorted(root.iterdir()):
            shutil.copytree(task, TASKS / task.name, symlinks=True)
            print(f"wrote evals/tasks/{task.name}")


if __name__ == "__main__":
    main()
