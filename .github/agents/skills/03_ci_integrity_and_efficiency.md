# Skill: CI Integrity and Efficiency

## Objective

Maintain code integrity by running deterministic checks before merge.

## Required CI Signals

- PR governance checks pass
- Repository integrity checks pass
- Python sanity checks pass when source files exist
- Test job passes when tests exist

## Efficiency Principles

- Skip expensive jobs when not applicable
- Run conditional tests based on changed file scope
- Keep workflows deterministic and fast to reduce feedback time

## Guardrails

- Never merge with failing required checks
- Never bypass CI with direct commits to protected branches

