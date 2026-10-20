"""Master evaluation runner for Phase 13.

Usage:
  python evaluation/run_evaluation.py                       # run all areas
  python evaluation/run_evaluation.py --list                # list areas and exit
  python evaluation/run_evaluation.py --only forecasting    # run one area
  python evaluation/run_evaluation.py --with-llm            # enable LLM checks
  python evaluation/run_evaluation.py --with-gt-sim         # enable GT revenue simulation

Areas: forecasting, segmentation, elasticity, pricing, llm_layer, system_performance
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

# Ensure evaluation/ directory is on the path so sibling modules import cleanly
# regardless of whether the script is invoked from the repo root or from evaluation/.
_EVAL_ROOT = Path(__file__).resolve().parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from utils import RESULTS_DIR, ensure_results_dir  # noqa: E402

logger = logging.getLogger(__name__)

AREAS: list[str] = [
    "forecasting",
    "segmentation",
    "elasticity",
    "pricing",
    "llm_layer",
    "system_performance",
]

# Map area name -> module name (all in evaluation/)
AREA_MODULES: dict[str, str] = {
    "forecasting": "forecasting_eval",
    "segmentation": "segmentation_eval",
    "elasticity": "elasticity_eval",
    "pricing": "pricing_eval",
    "llm_layer": "llm_layer_eval",
    "system_performance": "system_performance_eval",
}


def _import_area(area: str):
    """Lazy-import an evaluation module by area name."""
    module_name = AREA_MODULES[area]
    import importlib  # noqa: PLC0415
    return importlib.import_module(module_name)


def _run_area(area: str, args: SimpleNamespace) -> dict:
    """Run one area and return a result dict with status and elapsed time."""
    t0 = time.perf_counter()
    status = "FAIL"
    error_msg = ""
    try:
        module = _import_area(area)
        module.run(args)
        status = "PASS"
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error("  [%s] FAILED: %s", area, error_msg, exc_info=True)
    elapsed = time.perf_counter() - t0
    return {
        "area": area,
        "status": status,
        "elapsed_seconds": round(elapsed, 2),
        "error": error_msg,
    }


def _collect_output_files() -> list[str]:
    """List all files currently in evaluation/results/."""
    return sorted(
        str(p.relative_to(RESULTS_DIR.parent)) for p in RESULTS_DIR.glob("*")
        if p.is_file() and p.name != ".gitkeep"
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Phase 13 evaluation runner — measures system performance; never modifies it."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available evaluation areas and exit.",
    )
    parser.add_argument(
        "--only",
        metavar="AREA",
        choices=AREAS,
        help="Run only the specified area.",
    )
    parser.add_argument(
        "--with-llm",
        action="store_true",
        default=False,
        help=(
            "Enable live LLM API calls in llm_layer evaluation.  "
            "OFF by default because it makes paid API calls.  "
            "Requires LLM_API_KEY to be set in the environment."
        ),
    )
    parser.add_argument(
        "--with-gt-sim",
        action="store_true",
        default=False,
        help=(
            "Enable optional ground-truth revenue simulation in pricing evaluation.  "
            "OFF by default."
        ),
    )

    parsed = parser.parse_args()

    if parsed.list:
        print("Available evaluation areas:")
        for area in AREAS:
            print(f"  {area}")
        return

    # Build args namespace to pass into each run() function
    run_args = SimpleNamespace(
        with_llm=parsed.with_llm,
        with_gt_sim=parsed.with_gt_sim,
    )

    ensure_results_dir()
    areas_to_run = [parsed.only] if parsed.only else AREAS

    print(f"\n{'='*60}")
    print(f"Phase 13 Evaluation — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Areas: {', '.join(areas_to_run)}")
    if parsed.with_llm:
        print("  [--with-llm] LLM API calls enabled")
    if parsed.with_gt_sim:
        print("  [--with-gt-sim] Ground-truth revenue simulation enabled")
    print(f"{'='*60}\n")

    results = []
    for area in areas_to_run:
        print(f"--- Running: {area} ---")
        result = _run_area(area, run_args)
        results.append(result)
        status_sym = "✓" if result["status"] == "PASS" else "✗"
        print(f"  {status_sym} {area}: {result['status']} ({result['elapsed_seconds']:.1f}s)\n")

    # Summary table
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    total_pass = sum(1 for r in results if r["status"] == "PASS")
    total_fail = sum(1 for r in results if r["status"] == "FAIL")
    for r in results:
        sym = "PASS" if r["status"] == "PASS" else "FAIL"
        print(f"  [{sym}] {r['area']:<25} {r['elapsed_seconds']:>7.1f}s")
    print(f"{'='*60}")
    print(f"  Total: {total_pass} passed, {total_fail} failed\n")

    # Save summary JSON
    summary = {
        "timestamp": datetime.now().isoformat(),
        "areas_run": areas_to_run,
        "with_llm": parsed.with_llm,
        "with_gt_sim": parsed.with_gt_sim,
        "results": results,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "output_files": _collect_output_files(),
    }
    summary_path = RESULTS_DIR / "evaluation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Summary saved to: {summary_path}")

    if total_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
