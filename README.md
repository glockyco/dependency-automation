# Dependency Automation

Central control plane for dependency updates that require repository write access.
Hosted Renovate remains the owner of native package managers and GitHub Actions.
This repository owns scheduled Nix updates that Renovate cannot complete with all
required generated state.

The repository is public so GitHub enforces branch protection on the personal
account plan. Its main branch requires the `Validate` check for every actor. No
credential is stored in Git, and pull-request workflows never receive the App
private key.

## Architecture

The private `glockyco-dependency-updater` GitHub App is the only publishing
identity. The App is installed only on managed repositories and has these
repository permissions:

- Metadata: read
- Contents: read and write
- Pull requests: read and write

The App private key exists only as the `DEPENDENCY_UPDATER_PRIVATE_KEY` secret in
this repository. `DEPENDENCY_UPDATER_CLIENT_ID` is an Actions variable. Each
matrix job mints a token for one target repository. The token expires after one
hour and is revoked when the job ends.

This design keeps the App key out of every target repository. A compromised
target workflow cannot use the key to write to another managed repository. The
workflow does not use a personal access token or a target repository's default
workflow token.

`repositories.json` is the complete registry. Each entry declares:

- the target repository;
- one stable automation branch;
- the only paths that the update may change;
- commands as argument arrays, never shell text.

`automation.py` validates the registry, runs a complete `nix flake update`, and
fails if a command changes an undeclared path. The GitHub App then creates or
refreshes one review-only pull request. App-authored pull requests start the
target repository's normal CI. This repository does not merge them.

The controller is centralized, but dependency closure and verification remain
repository-owned. The registry includes a project-specific command only when a
Nix update must regenerate matching state. For example,
`erenshor-data-mining` synchronizes its exact pnpm assertion after updating the
flake lock. This is an explicit dependency boundary, not a second updater.

## Managed repositories

| Repository | Managed state | Extra regeneration |
| --- | --- | --- |
| `nix-config` | `flake.lock` | None |
| `omp-agent-setup` | `flake.lock` | None |
| `erenshor-data-mining` | `flake.lock`, `package.json` | Exact Nix-provided pnpm version |

Other repositories remain outside the App installation until their dependency
boundary and CI contract are reviewed:

| Repository | Current boundary |
| --- | --- |
| `ardenfall-compendium` | Nix toolchain plus Renovate-managed Bun dependencies |
| `ancient-kingdoms-mods` | Nix toolchain plus an exact pnpm assertion that needs one synchronized owner |
| `Teralizer` | Nix toolchain plus Gradle and Python project dependencies |
| `HotRepl` | No Nix flake; Renovate owns its supported dependency graphs |

## Operations

Run every managed update:

```sh
gh workflow run update-nix-dependencies.yml --repo glockyco/dependency-automation
```

Run one target:

```sh
gh workflow run update-nix-dependencies.yml \
  --repo glockyco/dependency-automation \
  -f repository=erenshor-data-mining
```

Inspect the run and generated pull requests:

```sh
gh run list --workflow update-nix-dependencies.yml \
  --repo glockyco/dependency-automation --limit 5
gh pr list --repo glockyco/erenshor-data-mining \
  --head automation/update-nix-dependencies
```

Before merge, inspect every changed lock or assertion and the dependency release
notes. Merge only after the target repository's required checks pass.

## Onboarding

Before adding a repository:

1. Map every manifest, lock, generated assertion, and automated owner.
1. Define the complete Nix update command sequence and its exact output paths.
1. Add deterministic CI checks that fail on stale or incomplete generated state.
1. Disable Renovate's Nix manager in the target repository.
1. Add one `repositories.json` entry and its contract tests.
1. Add the repository to the GitHub App installation.
1. Run one targeted update and verify the App author, changed paths, and normal CI.

Do not install the App before the local ownership and failure contracts exist.
Do not add a target-local copy of the App private key or another scheduled Nix
updater.

## Key rotation

1. Generate a new private key in the GitHub App settings.
1. Replace `DEPENDENCY_UPDATER_PRIVATE_KEY` in this repository.
1. Run one update for each managed repository and confirm token creation.
1. Delete the old key in the GitHub App settings.

Do not put the private key in Git, Nix, SOPS, a password manager, shell history,
or a local environment file. Delete the downloaded key after the repository
secret is set and the new key is verified.
