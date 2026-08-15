from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+$")
REQUIRED_KEYS = {"repository", "branch", "paths", "commands"}


class RegistryError(ValueError):
    """The managed-repository registry violates its contract."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RegistryError(f"Cannot read registry {path}: {error}") from error


def load_registry(path: Path) -> list[dict[str, Any]]:
    data = _load_json(path)
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise RegistryError("Registry schemaVersion must be 1")

    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise RegistryError("Registry repositories must be a non-empty list")

    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for entry in repositories:
        if not isinstance(entry, dict) or set(entry) != REQUIRED_KEYS:
            raise RegistryError(f"Repository entries must contain exactly {sorted(REQUIRED_KEYS)}")

        repository = entry["repository"]
        if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
            raise RegistryError(f"Invalid repository name: {repository!r}")
        if repository in seen:
            raise RegistryError(f"Duplicate repository: {repository}")
        seen.add(repository)

        branch = entry["branch"]
        if not isinstance(branch, str) or not branch.startswith("automation/"):
            raise RegistryError(f"Invalid automation branch for {repository}: {branch!r}")

        paths = entry["paths"]
        if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
            raise RegistryError(f"Paths for {repository} must be a unique non-empty list")
        for raw_path in paths:
            if not isinstance(raw_path, str):
                raise RegistryError(f"Invalid managed path for {repository}: {raw_path!r}")
            managed_path = PurePosixPath(raw_path)
            if managed_path.is_absolute() or ".." in managed_path.parts or raw_path in {"", "."}:
                raise RegistryError(f"Invalid managed path for {repository}: {raw_path!r}")

        commands = entry["commands"]
        if not isinstance(commands, list) or not commands:
            raise RegistryError(f"Commands for {repository} must be a non-empty list")
        for command in commands:
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(argument, str) and argument and "\0" not in argument for argument in command)
            ):
                raise RegistryError(f"Commands for {repository} must be non-empty argument arrays")
        if commands[0] != ["nix", "flake", "update"]:
            raise RegistryError(f"The first command for {repository} must update the complete flake lock")

        validated.append(entry)

    return validated


def select_repositories(registry: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    if target == "all":
        return registry
    selected = [entry for entry in registry if entry["repository"] == target]
    if not selected:
        raise RegistryError(f"Unknown repository: {target}")
    return selected


def changed_paths(checkout: Path) -> set[str]:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "--no-ext-diff"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return set(tracked) | set(untracked)


def update_repository(registry: list[dict[str, Any]], repository: str, checkout: Path) -> list[str]:
    entry = select_repositories(registry, repository)[0]
    if not checkout.is_dir():
        raise RegistryError(f"Checkout does not exist: {checkout}")

    for command in entry["commands"]:
        subprocess.run(command, cwd=checkout, check=True)

    changed = changed_paths(checkout)
    unexpected = sorted(changed - set(entry["paths"]))
    if unexpected:
        raise RegistryError(f"Update for {repository} changed unmanaged paths: {', '.join(unexpected)}")
    return sorted(changed)


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Manage repository Nix update contracts")
    command_parser.add_argument(
        "--registry",
        type=Path,
        default=Path(__file__).with_name("repositories.json"),
    )
    subparsers = command_parser.add_subparsers(dest="command", required=True)

    matrix_parser = subparsers.add_parser("matrix", help="Emit a GitHub Actions matrix")
    matrix_parser.add_argument("--target", default="all")

    update_parser = subparsers.add_parser("update", help="Run and validate one repository update")
    update_parser.add_argument("--repository", required=True)
    update_parser.add_argument("--checkout", type=Path, required=True)
    return command_parser


def main() -> int:
    arguments = parser().parse_args()
    try:
        registry = load_registry(arguments.registry)
        if arguments.command == "matrix":
            print(json.dumps({"include": select_repositories(registry, arguments.target)}, separators=(",", ":")))
        else:
            changed = update_repository(registry, arguments.repository, arguments.checkout)
            print(json.dumps({"repository": arguments.repository, "changed": changed}, separators=(",", ":")))
    except (RegistryError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
