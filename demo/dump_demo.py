"""
dump_demo.py -- create a mysqldump of both databases for demo use.

Run from the REPO ROOT:
    python demo/dump_demo.py

Writes:
    demo/revenue_management.sql.gz
    demo/revenue_management_gt.sql.gz

Prerequisites: mysqldump must be on PATH (ships with MySQL 8.0).
The script reads credentials from data-pipeline/.env.

The compressed dumps are gitignored because they exceed 50 MB.
Store them on Google Drive / OneDrive and share the link with the team.
See demo/README.md for the restore procedure.
"""
from __future__ import annotations

import gzip
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE  = REPO_ROOT / "data-pipeline" / ".env"
DEMO_DIR  = REPO_ROOT / "demo"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found.")
        sys.exit(1)
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def _dump(schema: str, out_path: Path, env: dict[str, str]) -> None:
    print(f"  Dumping {schema} -> {out_path.name} ...", end=" ", flush=True)
    cmd = [
        "mysqldump",
        f"--host={env.get('DB_HOST', 'localhost')}",
        f"--port={env.get('DB_PORT', '3306')}",
        f"--user={env['DB_USER']}",
        f"--password={env['DB_PASSWORD']}",
        "--single-transaction",
        "--routines",
        "--triggers",
        schema,
    ]
    with gzip.open(out_path, "wb") as gz:
        result = subprocess.run(cmd, stdout=gz, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print("FAILED")
        print(result.stderr.decode(errors="replace"))
        sys.exit(result.returncode)
    size_mb = out_path.stat().st_size / 1_048_576
    print(f"done  ({size_mb:.1f} MB compressed)")


def main() -> None:
    print("\nDemo database dump\n")
    env = _load_env()
    DEMO_DIR.mkdir(exist_ok=True)

    for schema, filename in [
        (env.get("DB_NAME",    "revenue_management"),    "revenue_management.sql.gz"),
        (env.get("DB_GT_NAME", "revenue_management_gt"), "revenue_management_gt.sql.gz"),
    ]:
        _dump(schema, DEMO_DIR / filename, env)

    print("\nDump complete.")
    print(f"  Files in: {DEMO_DIR.resolve()}")
    print("  NOTE: These files are gitignored (>50 MB).")
    print("        Upload to shared storage and record the link in demo/README.md.\n")


if __name__ == "__main__":
    main()
