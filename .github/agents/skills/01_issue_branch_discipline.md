# Skill: Issue-Branch Discipline

## Objective

Guarantee that every branch corresponds to a single tracked GitHub issue.

## Required Inputs

- Issue number
- Issue title and acceptance criteria
- Workstream label and milestone

## Execution Checklist

- [ ] Branch name follows `<type>/<issue-number>-<slug>`
- [ ] Branch issue number exists in repository issues
- [ ] PR body includes `Closes #<issue-number>`
- [ ] Issue labels match the touched workstream

## Anti-Patterns

- Branch names with no issue number
- Multi-issue changes in one branch without explicit parent issue
- PRs with no closure keyword (`Closes`, `Fixes`, `Resolves`)

