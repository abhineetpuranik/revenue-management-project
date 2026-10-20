"""
run_pipeline.py — cross-platform batch pipeline runner for the
AI-Powered Demand Forecasting and Dynamic Pricing project.

Run from the REPO ROOT (not data-pipeline/):
    python scripts/run_pipeline.py          # run every stage in order
    python scripts/run_pipeline.py --list   # print stages and exit
    python scripts/run_pipeline.py --only train_model
    python scripts/run_pipeline.py --from build_features

Stages run inside data-pipeline/ with its own virtual environment
automatically located and activated via the subprocess PATH.

Requirements: Python 3.10-3.12. No extra dependencies beyond stdlib.
Does NOT start the Flask backend or Angular frontend — see README.md.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

# ── Repo layout ───────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / "data-pipeline"

# Python interpreter inside data-pipeline/venv (works on Windows & Unix)
if sys.platform == "win32":
    _VENV_PYTHON = PIPELINE_DIR / "venv" / "Scripts" / "python.exe"
else:
    _VENV_PYTHON = PIPELINE_DIR / "venv" / "bin" / "python"


# ── Stage registry ────────────────────────────────────────────────────────────
class Stage(NamedTuple):
    name: str
    module: str          # python -m <module>  (run from PIPELINE_DIR)
    description: str


STAGES: list[Stage] = [
    Stage(
        "generate_base",
        "data_generation.generate_base_tables",
        "Phase 1a — generate product, customer, calendar CSVs",
    ),
    Stage(
        "generate_transactional",
        "data_generation.generate_transactional_tables",
        "Phase 1b — generate price, sales, stock CSVs (~2 min)",
    ),
    Stage(
        "clean",
        "etl.clean_tables",
        "Phase 2a — clean and validate the six raw CSVs",
    ),
    Stage(
        "load_mysql",
        "etl.load_to_mysql",
        "Phase 2b — load cleaned data into MySQL",
    ),
    Stage(
        "build_features",
        "features.build_feature_table",
        "Phase 4  — build weekly feature table (lags + calendar + price)",
    ),
    Stage(
        "train_model",
        "models.train_forecasting_models",
        "Phase 5  — train LR baseline and XGBoost; save winner artifact",
    ),
    Stage(
        "estimate_elasticity",
        "pricing.estimate_elasticity",
        "Phase 7  — fit log-log OLS per product",
    ),
    Stage(
        "segment",
        "segmentation.run_segmentation",
        "Phase 6  — RFM + K-Means customer segmentation",
    ),
    Stage(
        "build_candidates",
        "pricing.build_candidates",
        "Phase 8a — generate candidate prices and apply constraints",
    ),
    Stage(
        "run_pricing",
        "pricing.run_pricing",
        "Phase 8b — score candidates and write recommendations",
    ),
    Stage(
        "generate_explanations",
        "explanations.generate_explanations",
        "Phase 9  — LLM explanation layer (mock or Gemini)",
    ),
]

_STAGE_MAP = {s.name: s for s in STAGES}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _hr() -> None:
    print("─" * 70)


def _check_venv() -> None:
    if not _VENV_PYTHON.exists():
        print(
            f"\nERROR: data-pipeline virtual environment not found.\n"
            f"  Expected: {_VENV_PYTHON}\n\n"
            f"  Create it:\n"
            f"    cd data-pipeline\n"
            f"    python -m venv venv\n"
            f"    {'venv\\Scripts\\Activate.ps1' if sys.platform == 'win32' else 'source venv/bin/activate'}\n"
            f"    pip install -r requirements.txt\n"
        )
        sys.exit(1)


def _check_env() -> None:
    env_file = PIPELINE_DIR / ".env"
    if not env_file.exists():
        print(
            f"\nERROR: {env_file} not found.\n"
            f"  Copy the example and fill in your MySQL credentials:\n"
            f"    {'copy' if sys.platform == 'win32' else 'cp'} "
            f"data-pipeline/.env.example data-pipeline/.env\n"
        )
        sys.exit(1)


def _run_stage(stage: Stage, *, dry_run: bool = False) -> None:
    _hr()
    print(f"  STAGE: {stage.name}")
    print(f"  {stage.description}")
    _hr()

    if dry_run:
        print("  (dry-run — skipped)")
        return

    cmd = [str(_VENV_PYTHON), "-m", stage.module]
    t0 = time.time()
    result = subprocess.run(
        cmd,
        cwd=str(PIPELINE_DIR),
        env={**os.environ, "PYTHONPATH": str(PIPELINE_DIR)},
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        _hr()
        print(
            f"\n  FAILED  stage={stage.name!r}  exit={result.returncode}"
            f"  ({elapsed:.1f}s)\n"
            f"  Stopping pipeline.  Fix the error above and rerun with:\n"
            f"    python scripts/run_pipeline.py --from {stage.name}\n"
        )
        sys.exit(result.returncode)

    _hr()
    print(f"  OK  {stage.name}  ({elapsed:.1f}s)\n")


def _list_stages() -> None:
    print("\nAvailable stages:\n")
    for i, s in enumerate(STAGES, 1):
        print(f"  {i:2d}.  {s.name:<26}  {s.description}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full data-pipeline or a subset of stages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--list", action="store_true",
        help="Print all stages and exit.",
    )
    group.add_argument(
        "--only", metavar="STAGE",
        help="Run a single named stage and exit.",
    )
    group.add_argument(
        "--from", dest="from_stage", metavar="STAGE",
        help="Run from this stage to the end (inclusive).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would run without executing.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.list:
        _list_stages()
        return

    # Validate stage name if given
    for flag_name, value in [("--only", args.only), ("--from", args.from_stage)]:
        if value and value not in _STAGE_MAP:
            valid = ", ".join(s.name for s in STAGES)
            print(f"\nERROR: Unknown stage {value!r} for {flag_name}.\n  Valid: {valid}\n")
            sys.exit(1)

    _check_venv()
    if not args.dry_run:
        _check_env()

    # Determine which stages to run
    if args.only:
        stages_to_run = [_STAGE_MAP[args.only]]
    elif args.from_stage:
        start_idx = next(i for i, s in enumerate(STAGES) if s.name == args.from_stage)
        stages_to_run = STAGES[start_idx:]
    else:
        stages_to_run = list(STAGES)

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Running {len(stages_to_run)} stage(s):")
    for s in stages_to_run:
        print(f"  • {s.name}")
    print()

    t_start = time.time()
    for stage in stages_to_run:
        _run_stage(stage, dry_run=args.dry_run)

    total = time.time() - t_start
    _hr()
    print(
        f"\n  ALL {len(stages_to_run)} STAGE(S) COMPLETED SUCCESSFULLY"
        f"  (total {total:.0f}s = {total / 60:.1f} min)\n"
    )


if __name__ == "__main__":
    main()
