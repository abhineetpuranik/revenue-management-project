# Git workflow

- Don't push to `main` directly. Everything goes through a pull request.
- Make one branch per phase, for example `feature/segmentation` or `feature/api-pricing`. Use `chore/...` for small fixes.
- Someone other than the author reviews and merges the PR.
- Only merge when the phase runs and `pytest tests -v` passes.
- Delete the branch after merging.

## Starting work

```bash
git checkout main
git pull origin main
git checkout -b feature/<name>
```

Commit as you go, then:

```bash
git push -u origin feature/<name>
```

Open a PR into `main` and write what you did and how to test it.

If your work depends on a branch that isn't merged yet, open the PR against that branch instead of `main`. Once the other PR is merged and its branch deleted, GitHub moves yours to `main`.

## Conflicts

Most conflicts come from `database/schema.sql` and `data-pipeline/requirements.txt`. Pull `main` into your branch before opening a PR. If two branches both added a line, keep both lines and remove the `<<<<<<<`, `=======` and `>>>>>>>` markers.

## Don't commit

- `venv/`, `node_modules/`, a real `.env` file
- `data-pipeline/data/raw` and `data/cleaned`
- output CSVs where only the timestamp changed after a re-run (undo with `git checkout -- data-pipeline/data`)

## Ground truth

Only the `validate_*.py` files may read `revenue_management_gt`. The tests check this.
