# Dependency Automation

Dependency Automation opens Nix dependency update pull requests for the glockyco repositories listed in [repositories.json](repositories.json). It is a GitHub Actions controller, not an updater to install in each project. Hosted Renovate handles native package managers and GitHub Actions separately.

## Run updates

The [update workflow](.github/workflows/update-nix-dependencies.yml) runs on a schedule. To start it manually, use the GitHub CLI with an account that can dispatch workflows in this repository:

```sh
gh workflow run update-nix-dependencies.yml --repo glockyco/dependency-automation
```

To update one target, pass its name from the registry:

```sh
gh workflow run update-nix-dependencies.yml \
  --repo glockyco/dependency-automation \
  -f repository=erenshor-data-mining
```

Inspect the run and the target's pull request:

```sh
gh run list --workflow update-nix-dependencies.yml \
  --repo glockyco/dependency-automation --limit 5
gh pr list --repo glockyco/erenshor-data-mining \
  --head automation/update-nix-dependencies
```

Before merging, review every changed lock or generated assertion and the dependency release notes. Merge only after the target repository's required checks pass.

## What it changes

[repositories.json](repositories.json) defines the targets, automation branches, allowed output paths and update commands. [automation.py](automation.py) runs a complete Nix flake update and any declared regeneration commands. It fails if an update changes a path outside that target's allowlist.

The workflow uses a repository-scoped GitHub App token to create or refresh one review-only pull request per target. It does not merge pull requests or activate the updated configuration. App-authored pull requests start the target's normal CI.

## Configure access

The workflow needs the `glockyco-dependency-updater` GitHub App installed on each target. Set this repository's Actions variable `DEPENDENCY_UPDATER_CLIENT_ID` and Actions secret `DEPENDENCY_UPDATER_PRIVATE_KEY` from that App. The workflow requests contents and pull-request write access for one target per job.

Keep the private key only in this repository's Actions secrets, not in target repositories. Pull-request validation does not receive the key. [AGENTS.md](AGENTS.md) defines the security boundaries for changes to the controller.

To rotate the key:

1. Generate a new private key in the GitHub App settings.
2. Replace `DEPENDENCY_UPDATER_PRIVATE_KEY` in this repository.
3. Run one update for each registered target and confirm token creation.
4. Delete the old key in the GitHub App settings.

Do not put the key in Git, Nix, SOPS, a password manager, shell history or a local environment file. Delete the downloaded key after the repository secret is set and the new key is verified.

## Add a repository

1. Identify each dependency manifest, lock file, generated assertion and existing updater so their responsibilities do not overlap.
2. Define the complete Nix update command sequence and its exact output paths.
3. Add deterministic CI checks to the target that fail on stale or incomplete generated state.
4. Disable Renovate's Nix manager in the target.
5. Add an entry to [repositories.json](repositories.json) and contract tests in [tests/test_automation.py](tests/test_automation.py).
6. Add the target to the GitHub App installation.
7. Run one targeted update and verify the App author, changed paths and normal CI.

Do not install the App before the target's update and failure contracts exist. Do not add another scheduled Nix updater, as it would compete with this controller.

## Development

Use Python 3 and actionlint. Run the same checks as [CI](.github/workflows/ci.yml):

```sh
python3 -m unittest discover -s tests -v
actionlint
```

[AGENTS.md](AGENTS.md) covers change boundaries and the live verification required when adding a target.
