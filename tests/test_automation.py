from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from automation import RegistryError, load_registry, select_repositories, update_repository


class AutomationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_registry(self, repositories: list[dict[str, object]]) -> Path:
        path = self.root / "repositories.json"
        path.write_text(json.dumps({"schemaVersion": 1, "repositories": repositories}), encoding="utf-8")
        return path

    @staticmethod
    def entry(repository: str = "example") -> dict[str, object]:
        return {
            "repository": repository,
            "branch": "automation/update-nix-dependencies",
            "paths": ["flake.lock"],
            "commands": [["nix", "flake", "update"]],
        }

    def test_registry_accepts_argument_arrays_and_selects_one_repository(self) -> None:
        registry = load_registry(self.write_registry([self.entry("first"), self.entry("second")]))

        self.assertEqual([entry["repository"] for entry in select_repositories(registry, "all")], ["first", "second"])
        self.assertEqual(select_repositories(registry, "second")[0]["repository"], "second")

    def test_registry_rejects_shell_commands(self) -> None:
        entry = self.entry()
        entry["commands"] = ["nix flake update"]

        with self.assertRaisesRegex(RegistryError, "argument arrays"):
            load_registry(self.write_registry([entry]))

    def test_registry_rejects_paths_outside_the_checkout(self) -> None:
        entry = self.entry()
        entry["paths"] = ["../other-repository"]

        with self.assertRaisesRegex(RegistryError, "Invalid managed path"):
            load_registry(self.write_registry([entry]))

    def initialize_checkout(self) -> Path:
        checkout = self.root / "checkout"
        checkout.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=checkout, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=checkout, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=checkout, check=True)
        (checkout / "flake.lock").write_text("old\n", encoding="utf-8")
        subprocess.run(["git", "add", "flake.lock"], cwd=checkout, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "initial"], cwd=checkout, check=True)
        return checkout

    def test_update_accepts_only_managed_changes(self) -> None:
        checkout = self.initialize_checkout()
        registry = [
            {
                **self.entry(),
                "commands": [
                    [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('flake.lock').write_text('new\\n')",
                    ]
                ],
            }
        ]

        self.assertEqual(update_repository(registry, "example", checkout), ["flake.lock"])

    def test_update_fails_when_a_command_changes_an_unmanaged_path(self) -> None:
        checkout = self.initialize_checkout()
        registry = [
            {
                **self.entry(),
                "commands": [
                    [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('README.md').write_text('unexpected\\n')",
                    ]
                ],
            }
        ]

        with self.assertRaisesRegex(RegistryError, "README.md"):
            update_repository(registry, "example", checkout)


if __name__ == "__main__":
    unittest.main()
