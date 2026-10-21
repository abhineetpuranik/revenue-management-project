#!/usr/bin/env python3
"""Assemble final-report.md from chapter files."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

CHAPTERS = [
    "front-matter.md",
    "ch01-introduction.md",
    "ch02-literature-review.md",
    "ch03-requirements.md",
    "ch04-system-design.md",
    "ch05-implementation.md",
    "ch06-testing-evaluation.md",
    "ch07-conclusion.md",
    "references.md",
    "appendices.md",
]

parts = []
for name in CHAPTERS:
    path = os.path.join(BASE, name)
    with open(path, "r", encoding="utf-8") as f:
        parts.append(f.read())
    print(f"  + {name} ({os.path.getsize(path)} bytes)")

assembled = "\n\n---\n\n".join(parts)
out_path = os.path.join(BASE, "final-report.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(assembled)

print(f"\nAssembled: {out_path}")
print(f"Total size: {len(assembled):,} chars")
