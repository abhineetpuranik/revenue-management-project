# Contributing Guide

The Git workflow for this project. All three contributors follow it so `main` always works and merges stay painless.

---

## Branches

- **`main` is protected and always working.** No direct pushes; changes arrive only through a reviewed Pull Request.
- **One branch per phase or sub-phase**, named `feature/<what>`. Small housekeeping changes use `chore/<what>`.

| Work | Branch used |
|---|---|
| Phase 1 dataset generation | `feature/dataset-generation` |
| Phase 2 ETL | `feature/etl-pipeline` |
| Phase 5 forecasting | `feature/demand-forecasting` |
| Phase 6 segmentation | `feature/segmentation` |
| Phase 7 elasticity | `feature/elasticity` |
| Phase 8 pricing | `feature/pricing-optimization` |
| Phase 9 LLM layer | `feature/llm-explanations` |
| Phase 10 API | `feature/api-<group>` |
| Phase 11 dashboard | `feature/dashboard-<view>` |

### Start a branch

```bash
git checkout main
git pull origin main
git checkout -b feature/<name>
# ... work, commit often ...
git push -u origin feature/<name>
```

After the first push, plain `git push` is enough.

---

## Pull Requests

1. Push the branch and open a PR into `main`.
2. In the description, say **what** was built, **how to run and test it**, and any **assumptions or limitations**.
3. At least one other teammate reviews; the reviewer merges, not the author.
4. After merging, click **Delete branch**, then everyone syncs: `git checkout main && git pull origin main`.

**A phase may only merge once it runs end to end and `pytest tests -v` passes.**

### Stacked PRs (when one phase needs another that isn't merged yet)

Open the dependent PR with the **unmerged branch as its base**, not `main`. Example: Phase 8 based on `feature/elasticity`. When the base PR merges **and its branch is deleted**, GitHub retargets the dependent PR to `main` automatically. Merge in dependency order.

---

## Avoiding and fixing conflicts

- **Shared files** are where conflicts happen: `database/schema.sql`, `data-pipeline/requirements.txt`, `.env.example`, `.gitignore`. Pull `main` into your branch before opening a PR: `git pull origin main`.
- **`schema.sql`:** add new tables to the section for your area (app tables in section 2, model-output tables in section 4), not just at the very end of the file, so parallel branches don't edit the same lines.
- **`requirements.txt`:** if two branches both added a package, keep both lines ("Accept both changes" in GitHub's conflict editor), then delete the `<<<<<<<`, `=======` and `>>>>>>>` lines.
- Never leave conflict markers in a file. Search for `<<<<<<<` before committing a merge.

---

## What not to commit

- `venv/`, `node_modules/`, `__pycache__/` (already in `.gitignore`)
- any real `.env` file (only `.env.example`)
- `data-pipeline/data/raw/` and `data/cleaned/` (regenerate them; see README)
- output CSVs whose only change is the timestamp after a re-run. Discard with `git checkout -- data-pipeline/data`
- downloaded files such as `*.bundle`

Run `git status` before every commit and read the list.

---

## Ground-truth rule

`revenue_management_gt` (`true_elasticity`, `true_segment`) may only be read by `validate_*.py` files. Each module has a test that fails if anything else references it. Keep it that way, or the evaluation becomes meaningless.

---

## Commit messages

Imperative mood, subject under 72 characters, optional body explaining *why*:

```
Phase 7: price elasticity estimation
Fix null handling in ETL date parser
```
