"""Just enough of Docker Compose to reproduce what `docker compose up` gives the PDP.

Reads the agent's compose file the way Compose v2 does for the parts that decide
what the Cerbos container sees: variable interpolation (from the invoking
environment, then the project `.env`), the service `environment` and `env_file`,
`command`/`entrypoint`, and `volumes`/`tmpfs`. Nothing here runs Docker.
"""

import re
import shlex
from pathlib import Path

import yaml

PROJECT = Path("/workspace")
CERBOS_IMAGE = "ghcr.io/cerbos/cerbos"
# Image defaults from `docker inspect ghcr.io/cerbos/cerbos:0.55.0`.
IMAGE_ENTRYPOINT = ["/cerbos"]
IMAGE_CMD = ["server"]
IMAGE_ENV = {"CERBOS_CONFIG": "__default__"}

COMPOSE_NAMES = (
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
)

_VAR = re.compile(
    r"\$(?:(?P<escaped>\$)|\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:(?P<op>:?[-?+])(?P<arg>[^}]*))?\}|(?P<named>[A-Za-z_][A-Za-z0-9_]*))"
)


class ComposeError(Exception):
    pass


def compose_file() -> Path:
    for name in COMPOSE_NAMES:
        if (PROJECT / name).is_file():
            return PROJECT / name
    raise ComposeError("no compose file in /workspace")


def parse_env_file(path: Path) -> dict:
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def interpolate(value, env: dict):
    if isinstance(value, dict):
        return {k: interpolate(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate(v, env) for v in value]
    if not isinstance(value, str):
        return value

    def substitute(match):
        if match.group("escaped"):
            return "$"
        name = match.group("braced") or match.group("named")
        op, arg = match.group("op"), match.group("arg") or ""
        present = name in env
        current = env.get(name, "")
        if op in (":-", "-"):
            use_default = (not present) or (op == ":-" and current == "")
            return interpolate(arg, env) if use_default else current
        if op in (":?", "?"):
            missing = (not present) or (op == ":?" and current == "")
            if missing:
                raise ComposeError(f"required variable {name} is missing: {arg}")
            return current
        if op in (":+", "+"):
            use_alt = present and (op == "+" or current != "")
            return interpolate(arg, env) if use_alt else ""
        return current

    return _VAR.sub(substitute, value)


def load(host_env: dict) -> dict:
    """Return the interpolated compose model."""
    path = compose_file()
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("services"), dict):
        raise ComposeError(f"{path.name} has no services mapping")
    env = {}
    if (PROJECT / ".env").is_file():
        env.update(parse_env_file(PROJECT / ".env"))
    env.update(host_env)
    return interpolate(raw, env)


def load_raw() -> dict:
    return yaml.safe_load(compose_file().read_text())


def cerbos_service(model: dict) -> tuple[str, dict]:
    matches = [
        (name, svc)
        for name, svc in model["services"].items()
        if isinstance(svc, dict)
        and str(svc.get("image", "")).startswith(CERBOS_IMAGE)
    ]
    if len(matches) != 1:
        raise ComposeError(
            f"expected exactly one service running {CERBOS_IMAGE}, found {len(matches)}"
        )
    return matches[0]


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def container_env(service: dict, host_env: dict) -> dict:
    env = dict(IMAGE_ENV)
    for entry in _as_list(service.get("env_file")):
        path = entry.get("path") if isinstance(entry, dict) else entry
        required = entry.get("required", True) if isinstance(entry, dict) else True
        file = (PROJECT / path).resolve()
        if file.is_file():
            env.update(parse_env_file(file))
        elif required:
            raise ComposeError(f"env_file {path} does not exist")
    declared = service.get("environment") or {}
    if isinstance(declared, list):
        items = []
        for item in declared:
            key, sep, value = str(item).partition("=")
            items.append((key, value if sep else None))
    else:
        items = list(declared.items())
    for key, value in items:
        if value is None:
            if key in host_env:
                env[key] = host_env[key]
            else:
                env.pop(key, None)
        else:
            env[key] = str(value)
    return env


def command(service: dict) -> list[str]:
    entrypoint = service.get("entrypoint")
    cmd = service.get("command")
    if isinstance(entrypoint, str):
        entrypoint = shlex.split(entrypoint)
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    if entrypoint is None:
        entrypoint = IMAGE_ENTRYPOINT
        if cmd is None:
            cmd = IMAGE_CMD
    return [str(x) for x in list(entrypoint) + list(cmd or [])]


def mounts(service: dict) -> list[dict]:
    """Normalise volumes and tmpfs into {type, source, target, read_only}."""
    result = []
    for entry in _as_list(service.get("volumes")):
        if isinstance(entry, dict):
            kind = entry.get("type", "volume")
            result.append(
                {
                    "type": kind,
                    "source": entry.get("source"),
                    "target": entry.get("target"),
                    "read_only": bool(entry.get("read_only", False)),
                }
            )
            continue
        parts = str(entry).split(":")
        if len(parts) == 1:
            result.append(
                {"type": "anonymous", "source": None, "target": parts[0], "read_only": False}
            )
            continue
        source, target = parts[0], parts[1]
        mode = parts[2] if len(parts) > 2 else ""
        kind = "bind" if source.startswith((".", "/", "~")) else "volume"
        result.append(
            {
                "type": kind,
                "source": source,
                "target": target,
                "read_only": "ro" in mode.split(","),
            }
        )
    for entry in _as_list(service.get("tmpfs")):
        result.append(
            {"type": "tmpfs", "source": None, "target": str(entry).split(":")[0], "read_only": False}
        )
    return result


def bind_source(mount: dict) -> Path:
    return (PROJECT / str(mount["source"])).resolve()


def host_path_for(container_path: str, service: dict) -> Path | None:
    """The workspace file a container path is bind-mounted from, if any."""
    best = None
    for mount in mounts(service):
        if mount["type"] != "bind" or not mount["target"]:
            continue
        target = mount["target"].rstrip("/")
        if container_path == target or container_path.startswith(target + "/"):
            if best is None or len(target) > len(best[0]):
                best = (target, mount)
    if best is None:
        return None
    target, mount = best
    return bind_source(mount) / container_path[len(target) :].lstrip("/")


def covering_mount(container_path: str, service: dict) -> dict | None:
    best = None
    path = container_path.rstrip("/")
    for mount in mounts(service):
        target = (mount["target"] or "").rstrip("/")
        if target and (path == target or path.startswith(target + "/")):
            if best is None or len(target) > len(best["target"].rstrip("/")):
                best = mount
    return best
