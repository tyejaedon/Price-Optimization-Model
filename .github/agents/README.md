# Workflow Governance Agent

This repository uses a policy agent implemented through GitHub Actions and repository conventions.

## Agent Purpose

The agent enforces process quality and code integrity by validating:

- issue-linked branch naming,
- draft-first pull request flow,
- issue linkage in PR body,
- CI readiness checks,
- protection against direct workflow bypass.

## Agent Components

- `.github/workflows/pr-governance.yml` - process policy checks for PRs
- `.github/workflows/ci-checks.yml` - code quality and repository integrity checks
- `.github/copilot-instructions.md` - instructions for AI-assisted contributions
- `CONTRIBUTING.md` - contributor-facing workflow rules and mapping
- `scripts/bootstrap-workflow.ps1` - branch and draft PR bootstrap from issue metadata
- `scripts/ready-pr.ps1` - required-check gate that marks draft PRs ready only when CI passes

## Skill Packs

See `.github/agents/skills/` for focused skill guidance used by humans and coding agents.

