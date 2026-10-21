# Report Build Instructions

`pandoc` was not found in this environment. Use one of the methods below to
convert `final-report.md` to a Word document (`.docx`).

---

## Option A — Install pandoc (recommended)

1. Install pandoc from <https://pandoc.org/installing.html>.
   - macOS: `brew install pandoc`
   - Windows: download the installer from the pandoc releases page.

2. From the `docs/report/` directory, run:

```bash
pandoc final-report.md \
  --output final-report.docx \
  --toc \
  --number-sections \
  --toc-depth=3 \
  --reference-doc=reference.docx
```

If you do not have a `reference.docx` template, omit `--reference-doc` and
pandoc will use its built-in defaults. To create a template for customising
fonts and spacing:

```bash
pandoc --print-default-data-file reference.docx > reference.docx
```

Then open `reference.docx` in Word, change fonts and paragraph styles to
match your department template, save it, and re-run the build command above.

**Recommended formatting (unless your department specifies otherwise):**
- Font: Times New Roman 12 pt body
- Line spacing: 1.5
- Margins: 1 inch (2.54 cm) all sides
- Front matter page numbers: Roman numerals (i, ii, iii …)
- Body page numbers: Arabic numerals restarting at 1

---

## Option B — Google Docs / Microsoft Word (manual)

1. Open `final-report.md` in VS Code or any Markdown editor.
2. Copy the content into a new Google Doc or Word document.
3. Apply heading styles (Heading 1, Heading 2, Heading 3) to match the
   Markdown heading levels (#, ##, ###).
4. Insert the figures from `docs/report/figures/` at the marked positions.
5. Insert the Mermaid diagrams (exported from `docs/report/diagrams/` — see
   below) at the marked positions.
6. Use Insert → Table of Contents to generate the ToC from heading styles.
7. Number pages: Roman numerals for front matter, Arabic from Chapter 1.

---

## Exporting Mermaid diagrams

The five diagram source files in `docs/report/diagrams/` are Mermaid (`.mmd`)
files. Export them to PNG or SVG using one of:

- **Mermaid Live Editor:** <https://mermaid.live> — paste the `.mmd` content,
  click Download SVG or PNG.
- **VS Code extension:** Install the "Mermaid Preview" extension, open the
  `.mmd` file, and export.
- **CLI (requires Node.js):**
  ```bash
  npm install -g @mermaid-js/mermaid-cli
  mmdc -i architecture.mmd -o architecture.png -w 1200
  ```

Diagrams to export:
- `architecture.mmd` → Figure 1: System Architecture
- `data-flow.mmd` → Figure 2: Data Flow
- `er-diagram.mmd` → Figure 3: Entity-Relationship Diagram
- `pricing-flow.mmd` → Figure 4: Pricing Optimisation Flow
- `dataset-generation.mmd` → Figure 5: Dataset Generation Dependencies

Place exported images in `docs/report/figures/` and insert them into the
Word document at the `[FIGURE X]` placeholders in the chapter files.

---

## Re-assembling after edits

If you edit individual chapter files and want to regenerate `final-report.md`:

```bash
cd docs/report
python3 assemble.py
```

---

## Checklist before final submission

- [ ] All `[TEAM TO FILL: ...]` placeholders replaced with real content
- [ ] All `[TEAM TO CONFIRM: ...]` items verified against your synopsis
- [ ] All `[CITATION NEEDED: ...]` items resolved with real references
- [ ] All `[PENDING: run evaluation/run_evaluation.py]` items filled after
      running the evaluation with a live database
- [ ] All 6 dashboard screenshots captured (see `figure-and-screenshot-list.md`)
- [ ] All 5 Mermaid diagrams exported and inserted
- [ ] Table of contents updated in the Word document
- [ ] Page numbers correct (Roman for front matter, Arabic from Chapter 1)
- [ ] Spell-check and grammar check completed
