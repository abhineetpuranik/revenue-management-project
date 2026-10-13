import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from pricing.elasticity_model import fit_all, fit_product


def _synthetic_weeks(beta: float, n: int = 156, seed: int = 0, price_std: float = 0.1,
                     noise: float = 0.05) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    lpr = rng.normal(0, price_std, n)
    promo = rng.integers(0, 3, n)
    seas = np.log(rng.uniform(0.8, 1.3, n))
    fest = rng.integers(0, 2, n)
    log_units = 5 + beta * lpr + 0.1 * promo + 1.0 * seas + 0.2 * fest + rng.normal(0, noise, n)
    return pd.DataFrame({"product_id": "PX", "category": "Test", "units_sold": np.exp(log_units),
                         "log_price_ratio": lpr, "promo_days": promo,
                         "log_seasonal": seas, "festival_days": fest})


def test_recovers_known_elasticity():
    for beta in (-0.5, -1.0, -2.0):
        res = fit_product(_synthetic_weeks(beta))
        assert abs(res["elasticity"] - beta) < 0.05, res
        assert res["ci_low"] < beta < res["ci_high"]
        assert res["reliable_flag"] == 1


def test_positive_beta_flagged_unreliable():
    res = fit_product(_synthetic_weeks(+0.8))
    assert res["reliable_flag"] == 0
    assert "POSITIVE_BETA" in res["unreliable_reasons"]


def test_flat_price_flagged_low_variation():
    res = fit_product(_synthetic_weeks(-1.0, price_std=0.001, noise=0.001))
    assert "LOW_PRICE_VARIATION" in res["unreliable_reasons"]


def test_too_few_observations():
    res = fit_product(_synthetic_weeks(-1.0, n=20))
    assert res["reliable_flag"] == 0
    assert res["unreliable_reasons"] == "FEW_OBSERVATIONS"


def test_constant_control_is_dropped_not_singular():
    df = _synthetic_weeks(-1.2)
    df["units_sold"] /= np.exp(0.2 * df["festival_days"])
    df["festival_days"] = 0
    res = fit_product(df)
    assert abs(res["elasticity"] + 1.2) < 0.05


def test_fit_all_is_deterministic():
    df = pd.concat([_synthetic_weeks(-0.7, seed=1).assign(product_id="P1"),
                    _synthetic_weeks(-1.7, seed=2).assign(product_id="P2")])
    a, b = fit_all(df), fit_all(df)
    pd.testing.assert_frame_equal(a, b)
    assert list(a["product_id"]) == ["P1", "P2"]


def test_ground_truth_isolation():
    forbidden = re.compile(r"revenue_management_gt|true_elasticity|gt_product_elasticity")
    for name in ["elasticity_data.py", "elasticity_model.py", "estimate_elasticity.py"]:
        src = (PIPELINE_ROOT / "pricing" / name).read_text(encoding="utf-8")
        hits = forbidden.findall(src)
        assert not hits, f"{name} references ground truth: {set(hits)}"
