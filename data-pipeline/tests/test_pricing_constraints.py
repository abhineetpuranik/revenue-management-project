import sys
from pathlib import Path

import pandas as pd

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from pricing.candidates import candidate_steps, generate_candidates
from pricing.constraints import (apply_constraints, check_elasticity_reliable,
                                 check_margin, check_max_change, check_price_range)


def test_margin_exactly_at_limit_passes():
    assert check_margin(10.0, 9.0, min_margin=0.10) == (True, None)


def test_margin_just_below_limit_fails():
    assert check_margin(9.99, 9.0, min_margin=0.10) == (False, "MARGIN")


def test_margin_below_cost_fails():
    assert check_margin(8.0, 9.0)[0] is False


def test_max_change_exactly_15pct_passes():
    assert check_max_change(115.0, 100.0, 0.15)[0]
    assert check_max_change(85.0, 100.0, 0.15)[0]


def test_max_change_just_outside_fails():
    assert check_max_change(115.01, 100.0, 0.15) == (False, "MAX_CHANGE")
    assert check_max_change(84.99, 100.0, 0.15) == (False, "MAX_CHANGE")


def test_price_range_edges():
    assert check_price_range(5.0, 5.0, 8.0, tolerance=0.0, allow_extrapolation=False)[0]
    assert check_price_range(8.0, 5.0, 8.0, tolerance=0.0, allow_extrapolation=False)[0]
    assert check_price_range(8.01, 5.0, 8.0, tolerance=0.0, allow_extrapolation=False) == (False, "PRICE_RANGE")
    assert check_price_range(4.99, 5.0, 8.0, tolerance=0.0, allow_extrapolation=False)[0] is False


def test_price_range_tolerance_and_extrapolation():
    assert check_price_range(8.1, 5.0, 8.0, tolerance=0.02, allow_extrapolation=False)[0]
    assert check_price_range(100.0, 5.0, 8.0, tolerance=0.0, allow_extrapolation=True)[0]


def test_unreliable_elasticity_allows_only_current_price():
    assert check_elasticity_reliable(10.0, 10.0, 0)[0]
    assert check_elasticity_reliable(10.5, 10.0, 0) == (False, "ELASTICITY_UNRELIABLE")
    assert check_elasticity_reliable(10.5, 10.0, 1)[0]


def _state(**over):
    base = dict(product_id="P1", current_price=10.0, unit_cost=5.0, hist_min_price=8.0,
                hist_max_price=12.0, reliable_flag=1)
    base.update(over)
    return pd.DataFrame([base])


def test_grid_spans_band_and_includes_current():
    steps = candidate_steps(0.15, 0.01)
    assert steps.min() == -15 and steps.max() == 15 and 0 in steps
    c = generate_candidates(_state(current_price=3.37))
    assert 3.37 in c["candidate_price"].values
    assert c["change_pct"].abs().max() <= 0.15 + 1e-12


def test_apply_constraints_marks_reasons():
    st = _state()
    out = apply_constraints(generate_candidates(st), st)
    row = out.set_index("step")
    assert row.loc[0, "passes_all"] == 1 and row.loc[0, "is_current"] == 1
    assert row.loc[-15, "passes_all"] == 1 and row.loc[15, "passes_all"] == 1
    st2 = _state(hist_min_price=9.5, hist_max_price=10.5)
    row2 = apply_constraints(generate_candidates(st2), st2).set_index("step")
    assert row2.loc[-15, "failed_reasons"] == "PRICE_RANGE"
    assert row2.loc[15, "failed_reasons"] == "PRICE_RANGE"
    st3 = _state(unit_cost=8.0)
    row3 = apply_constraints(generate_candidates(st3), st3).set_index("step")
    assert row3.loc[-15, "failed_reasons"] == "MARGIN"
    assert row3.loc[-11, "failed_reasons"] == ""
    st4 = _state(reliable_flag=0)
    row4 = apply_constraints(generate_candidates(st4), st4).set_index("step")
    assert row4["passes_all"].sum() == 1 and row4.loc[0, "passes_all"] == 1


def test_passing_rows_satisfy_every_rule():
    st = _state(current_price=10.0, unit_cost=9.2, hist_min_price=9.0, hist_max_price=11.0)
    out = apply_constraints(generate_candidates(st), st)
    ok = out[out["passes_all"] == 1]
    assert ((ok["candidate_price"] - 9.2) / ok["candidate_price"] >= 0.10 - 1e-9).all()
    assert ok["candidate_price"].between(9.0, 11.0).all()
    assert (out["passes_all"] == 0).any()
