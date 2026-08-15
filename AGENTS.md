# Repository Rules

## Scope

This repository is the privileged control plane for Nix dependency pull
requests. It stores automation policy, not application code.

## Security invariants

- Keep `DEPENDENCY_UPDATER_PRIVATE_KEY` only in this repository's Actions secrets.
- Mint one repository-scoped installation token per matrix job.
- Request only contents and pull-request write permissions.
- Represent update commands as argument arrays. Never execute registry values
  through a shell.
- Fail when an update changes a path outside its registry allowlist.
- Keep pull requests review-only. Never merge from an updater workflow.
- Pin every third-party Action to a complete commit SHA.

## Ownership

Hosted Renovate owns native package managers and GitHub Actions. This repository
owns only the Nix state listed in `repositories.json`. A target repository must
disable Renovate's Nix manager before onboarding.

The target repository owns dependency closure and CI. Add a post-update command
only when one Nix change requires matching generated state. Do not hide project
package management behind a generic controller abstraction.

## Verification

Run before each commit:

```sh
python3 -m unittest discover -s tests -v
actionlint
```

A registry change also requires a targeted live workflow run. Verify the App
identity, the complete changed-path set, and normal target CI before calling the
onboarding complete.

## Commit policy

Use Conventional Commits. Give every commit a body that explains why the change
exists. Keep one logical change in each commit.
