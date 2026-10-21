# Submission Checklist — Phase 14

Work through this list top to bottom before the final submission.

---

## 1. Resolve open items in the report

Open `docs/report/open-items.md` and complete every item:

- **18 × [TEAM TO FILL]** — names, roll numbers, supervisor, department, institution, dates, acknowledgements, contribution splits.
- **5 × [TEAM TO CONFIRM]** — verify problem statement and objectives match your approved synopsis.
- **17 × [CITATION NEEDED]** — add missing academic references to `docs/report/references.md`.
- **16 × [PENDING: run evaluation]** — fill after running `python evaluation/run_evaluation.py` with a live database.
- **6 × screenshots** — capture dashboard screens per `docs/report/figure-and-screenshot-list.md`.
- **5 × Mermaid diagrams** — export `.mmd` files in `docs/report/diagrams/` to PNG per `docs/report/BUILD-INSTRUCTIONS.md`.

---

## 2. Fill PENDING evaluation metrics

Requires a working MySQL database and XGBoost:

```bash
# macOS: install libomp for XGBoost
brew install libomp

# Copy and populate the .env file
cp data-pipeline/.env.example data-pipeline/.env
# Edit data-pipeline/.env with: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD,
# DB_NAME=revenue_management, DB_GT_NAME=revenue_management_gt

# Run the evaluation
cd evaluation
python run_evaluation.py
```

After running, update the `[PENDING]` sections in:
`docs/evaluation-report.md`, `docs/report/ch06-testing-evaluation.md`,
`docs/report/front-matter.md` (abstract), `docs/report/ch07-conclusion.md`.

---

## 3. Capture dashboard screenshots

```bash
# Terminal 1
cd backend && python app.py

# Terminal 2
cd frontend && npx ng serve
# -> http://localhost:4200
```

Capture the 6 screens in `docs/report/figure-and-screenshot-list.md` and
save to `docs/report/figures/`.

---

## 4. Export Mermaid diagrams

Use <https://mermaid.live> — paste each `.mmd` file, download as PNG, save
to `docs/report/figures/`. Five diagrams: architecture, data-flow, er-diagram,
pricing-flow, dataset-generation.

---

## 5. Build the Word document

Install pandoc (`brew install pandoc`) then:

```bash
cd docs/report
python3 assemble.py          # regenerate final-report.md after edits
pandoc final-report.md --output final-report.docx --toc --number-sections
```

Verify in Word:
- [ ] Table of contents with correct page numbers
- [ ] Roman numerals for front matter, Arabic from Chapter 1
- [ ] All figures inserted with captions
- [ ] No `[TEAM TO FILL]` or `[PENDING]` placeholders remain

---

## 6. Run all test suites

```bash
cd data-pipeline && python -m pytest tests/ -v   # 65 tests (6 skip without DB)
cd backend      && python -m pytest tests/ -v   # 87 tests
cd frontend     && npx ng build && npx ng test --watch=false  # 76 specs
```

---

## 7. Tag the final commit

Run these commands **only after all above steps are complete**:

```bash
git add docs/report/ docs/submission-checklist.md
git commit -m "docs(phase14): finalise report and resolve open items"
git tag -a v1.0-submission -m "Final submission — Phase 14 complete"
git push
git push origin v1.0-submission
```

---

## 8. What to hand in

| Item | Location | Format |
|---|---|---|
| Project report | `docs/report/final-report.docx` | Word or PDF |
| Source code | This repository | ZIP or GitHub link |
| Demo backup | `demo/` folder | See `docs/demo-script.md` |
| Declaration forms | `docs/report/front-matter.md` → certificate section | Printed + signed |

---

## Phase 14 status summary

| Deliverable | Status |
|---|---|
| Evaluation scripts (`/evaluation/`) | ✅ Complete (Phase 13) |
| Gap-filling pytest tests (6 files) | ✅ Complete (Phase 13) |
| Report chapters 1–7 + front matter + appendices | ✅ Draft — open items remain |
| Mermaid diagrams (5 `.mmd` files) | ✅ Written — need manual PNG export |
| Evaluation figures (4 PNGs in `docs/report/figures/`) | ✅ Copied |
| `final-report.md` assembled | ✅ Complete |
| Word export | ⏳ Needs pandoc install |
| Dashboard screenshots (6) | ⏳ Needs manual capture |
| PENDING evaluation metrics | ⏳ Needs live DB run |
| Open items resolved (67 total) | ⏳ Team to complete |
| Final git tag `v1.0-submission` | ⏳ After all above |
