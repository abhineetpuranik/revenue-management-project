"""Phase 13 — Item 12: ground-truth isolation across all application packages.

Static grep test confirming no application code reads ground-truth column
names.  Covers etl/, features/, models/, segmentation/, pricing/,
explanations/, backend/routes/, backend/services/.  No DB access.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

BACKEND_ROOT = PIPELINE_ROOT.parent / "backend"

# Ground-truth identifiers that must never appear in application code.
FORBIDDEN_PATTERN = re.compile(
    r"revenue_management_gt|true_elasticity|true_segment|gt_product_elasticity"
    r"|gt_customer_segment|purchase_rate|basket_mean|basket_std"
)

APP_PACKAGES = [
    PIPELINE_ROOT / "etl",
    PIPELINE_ROOT / "features",
    PIPELINE_ROOT / "models",
    PIPELINE_ROOT / "segmentation",
    PIPELINE_ROOT / "pricing",
    PIPELINE_ROOT / "explanations",
    BACKEND_ROOT / "routes",
    BACKEND_ROOT / "services",
]

# These files are ALLOWED to reference ground truth.  They are the GT loaders
# and the ETL chain / validation hooks that legitimately handle GT columns
# (the data generator bakes true_elasticity / true_segment / purchase_rate /
# basket_mean / basket_std into the raw product/customer CSVs, which the ETL
# must clean, validate, and route to the separate GT database).  Application
# DECISION logic (models / pricing / segmentation / explanations / backend
# routes & services) is NOT in this set and remains forbidden from reading
# GT.  Matched by basename only.
ALLOWED_FILES = {
    # --- GT loaders (FEAT-002 hard rule) ---
    "load_to_mysql.py",          # loads GT into the GT database
    "db_connection.py",          # defines get_gt_engine() for GT reads
    # --- Validation hooks that compare to GT (FEAT-002 hard rule) ---
    "validate_segmentation.py",  # segmentation validation vs. true_segment
    "validate_pricing.py",       # pricing validation vs. true_elasticity
    # --- ETL GT-handling chain (legitimate; see docs/known-issues.md KI-09) ---
    "cleaning.py",               # cleans raw product/customer which contain the
                                 # generated GT columns, prepping them for
                                 # load_to_mysql.py to route to the GT database
    "validation.py",             # ETL data-quality check on cleaned GT fields
                                 # (asserts true_elasticity < 0)
    # --- Elasticity validation hook (sibling of validate_pricing.py; uses
    #     get_gt_engine(), the proper GT read path; consistent with the
    #     existing test_pricing_optimizer.py `startswith("validate_")`
    #     convention) ---
    "validate_elasticity.py",    # validates estimated vs. true_elasticity
}


def test_no_ground_truth_in_app_packages():
    violations = []
    for pkg_dir in APP_PACKAGES:
        if not pkg_dir.exists():
            continue
        for py_file in sorted(pkg_dir.glob("*.py")):
            if py_file.name in ALLOWED_FILES:
                continue
            source = py_file.read_text(encoding="utf-8")
            hits = FORBIDDEN_PATTERN.findall(source)
            if hits:
                rel = py_file.relative_to(PIPELINE_ROOT.parent)
                violations.append(f"{rel}: {sorted(set(hits))}")
    assert not violations, (
        "Ground-truth references found in application code:\n" + "\n".join(violations)
    )
