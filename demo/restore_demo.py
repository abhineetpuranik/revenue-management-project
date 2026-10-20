"""
restore_demo.py -- restore both databases from compressed mysqldumps.

Run from the REPO ROOT:
    python demo/restore_demo.py

Reads from:
    demo/revenue_management.sql.gz
    demo/revenue_management_gt.sql.gz

WARNING: This drops and recreates both schemas. Run database/schema.sql first
if the schemas do not exist yet.
"""
from __future__ import annotations

import gzip
import subprocess
import sys
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parent.parent
ENV_FILE   = REPO_ROOT / "data-pipeline" / ".env"
DEMO_DIR   = REPO_ROOT / "demo"
SCHEMA_SQL = REPO_ROOT / "database" / "schema.sql"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found.  Copy data-pipeline/.env.example and fill in credentials.")
        sys.exit(1)
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def _mysql_cmd(env: dict[str, str]) -> list[str]:
    return [
        "mysql",
        f"--host={env.get('DB_HOST', 'localhost')}",
        f"--port={env.get('DB_PORT', '3306')}",
        f"--user={env['DB_USER']}",
        f"--password={env['DB_PASSWORD']}",
    ]


def _recreate_schema(env: dict[str, str]) -> None:
    print("  Recreating schema (drops existing data) ...", end=" ", flush=True)
    cmd = _mysql_cmd(env)
    with open(SCHEMA_SQL, "rb") as f:
        result = subprocess.run(cmd, stdin=f, capture_output=True)
    if result.returncode != 0:
        print("FAILED")
        print(result.stderr.decode(errors="replace"))
        sys.exit(result.returncode)
    print("done")


def _restore(dump_path: Path, schema: str, env: dict[str, str]) -> None:
    if not dump_path.exists():
        print(f"ERROR: {dump_path} not found.  Run demo/dump_demo.py first.")
        sys.exit(1)
    print(f"  Restoring {schema} from {dump_path.name} ...", end=" ", flush=True)
    cmd = _mysql_cmd(env) + [schema]
    with gzip.open(dump_path, "rb") as gz:
        result = subprocess.run(cmd, stdin=gz, capture_output=True)
    if result.returncode != 0:
        print("FAILED")
        print(result.stderr.decode(errors="replace"))
        sys.exit(result.returncode)
    print("done")


def main() -> None:
    print("\nDemo database restore\n")
    env = _load_env()

    _recreate_schema(env)

    for schema, filename in [
        (env.get("DB_NAME",    "revenue_management"),    "revenue_management.sql.gz"),
        (env.get("DB_GT_NAME", "revenue_management_gt"), "revenue_management_gt.sql.gz"),
    ]:
        _restore(DEMO_DIR / filename, schema, env)

    print("\nRestore complete.  Start the backend with: cd backend && python app.py\n")


if __name__ == "__main__":
    main()
