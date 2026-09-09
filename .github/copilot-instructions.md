# Copilot Agent Instructions

These instructions define the default workflow behavior for coding agents and contributors in this repository.

## Mandatory Workflow Rules

1. **Issue-first development**
   - Every code change must map to an existing GitHub issue.
   - Use branch names that include the issue number.

2. **Branch naming convention**
   - Allowed format: `<type>/<issue-number>-<short-slug>`
   - Allowed types: `feature`, `fix`, `chore`, `docs`, `refactor`, `test`
   - Example: `feature/14-fastapi-health-endpoint`

3. **No direct commits to protected branch**
   - Never commit directly to `master` or `main`.
   - Use topic branches only.

4. **Draft PR required**
   - PRs must be opened as **Draft** first.
   - Convert to Ready for Review only after local checks and CI pass.

5. **PR must link issue and milestone**
   - PR body must include `Closes #<issue-number>` matching the branch issue number.
   - PR must declare the target milestone in the PR template field.

6. **CI must pass before merge**
   - All required GitHub Actions checks must pass.
   - Failing checks block merge.

7. **Data safety guardrail**
   - Do not commit files under `Data/`.
   - Keep large local datasets and generated data artifacts out of VCS.

## Default Task Flow for Agents

1. Validate issue scope and acceptance criteria.
2. Create/checkout issue branch using the naming rule.
3. Implement focused changes linked to that issue only.
4. Run local checks and tests.
5. Open Draft PR with linked issue and milestone.
6. Wait for CI + review approval before merge.

## Required References

- `CONTRIBUTING.md`
- `.github/pull_request_template.md`
- `Docs/Project_Milestones_and_Issues.md`
- `Docs/Blueprint.md`

