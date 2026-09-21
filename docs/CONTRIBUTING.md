# Contributing Guide

This document describes the Git workflow for the Revenue Management project.
All three contributors must follow these conventions to keep the repo clean and avoid merge conflicts.

---

## Branch Strategy

### Protected `main` branch

- `main` is the stable, verified branch.
- **No direct pushes to `main` are allowed.**
- All changes must arrive via a Pull Request that has been reviewed and approved by at least one other contributor before merging.

### Feature branches

Create one branch per phase/module, named with the `feature/` prefix:

```
feature/<phase-name>
```

Examples:

| Work being done | Branch name |
|---|---|
| Synthetic dataset generation | `feature/dataset-generation` |
| ETL and data cleaning | `feature/etl-pipeline` |
| Demand forecasting models | `feature/demand-forecasting` |
| Customer segmentation | `feature/customer-segmentation` |
| Price elasticity & optimisation | `feature/pricing-optimisation` |
| Flask API routes | `feature/api-routes` |
| Angular dashboard components | `feature/dashboard-components` |
| Database schema DDL | `feature/database-schema` |

### Creating and pushing a feature branch

```bash
# Start from an up-to-date main
git checkout main
git pull origin main

# Create your feature branch
git checkout -b feature/<phase-name>

# ... do your work, commit regularly ...

# Push and set up remote tracking
git push -u origin feature/<phase-name>
```

---

## Pull Request Workflow

1. Push your feature branch to origin (see above).
2. Open a Pull Request (PR) against `main`.
3. Write a short PR description covering:
   - What was implemented.
   - How to test / verify the change.
   - Any known limitations or follow-up tasks.
4. Request a review from at least one other contributor.
5. Address any review comments, then re-request review.
6. The reviewer merges the PR once satisfied — the author does **not** self-merge.
7. Delete the feature branch after a successful merge to keep the branch list tidy.

---

## Commit Messages

Use the imperative mood and keep the subject line under 72 characters:

```
Add demand forecasting XGBoost model
Fix null-handling in ETL date parser
Update health-check endpoint response format
```

For larger changes, add a blank line after the subject and a short body explaining *why*, not just *what*.

---

## Merge Policy

- Branches merge into `main` **only after** the corresponding phase is verified working end-to-end (all acceptance criteria from the phase spec are met).
- Squash-merging is acceptable for small, self-contained branches; use a regular merge commit for larger multi-commit branches so the history is readable.
- Rebasing feature branches on top of `main` is encouraged before opening a PR to minimise conflicts.

---

## Environment Setup Reminder

Before pushing, make sure:

- Python: `venv/` is **not** staged (`venv/` is in `.gitignore`).
- Node: `node_modules/` is **not** staged.
- Secrets: no real `.env` file is committed — only `.env.example` files.

Run `git status` and check the output before every commit.
