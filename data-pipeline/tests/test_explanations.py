"""
Phase 9 tests — payloads, guardrails, retry/fallback flow, isolation.

Run:  cd data-pipeline && pytest tests/test_explanations.py -v
(No API key or network needed — LLM calls use mock clients.)
"""
import re
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from explanations.fallback import fallback_text  # noqa: E402
from explanations.generate_explanations import RunStats, explain_one  # noqa: E402
from explanations.guardrails import check_output  # noqa: E402
from explanations.llm_client import LLMClient, LLMError, MockLLMClient  # noqa: E402
from explanations.payloads import pricing_payload, segment_payload, sensitivity_band  # noqa: E402
from explanations.prompts import SYSTEM_PROMPT, build_prompt  # noqa: E402

REC = {"product_id": "P013", "category": "Personal Care", "change_pct": -0.139,
       "revenue_change_pct": 0.0072, "binding_constraint": "MAX_CHANGE", "current_price": 15.57,
       "recommended_price": 13.40, "elasticity": -1.046, "expected_demand": 215.2,
       "baseline_demand": 183.9}
SEG = {"segment_label": "high_value", "customer_count": 160, "share_pct": 16.0,
       "revenue_share_pct": 40.06, "mean_frequency": 1037.05, "mean_monetary": 58087.23,
       "median_recency_days": 1.0}


def P():
    return pricing_payload(REC, 0.15)


# ── payloads ──────────────────────────────────────────────────────────────────
def test_pricing_payload_is_preformatted_and_unsigned():
    p = P()
    assert p["action"] == "cut" and p["price_change"] == "13.9%"
    assert p["revenue_direction"] == "increase" and p["revenue_change"] == "0.7%"
    assert p["price_sensitivity"] == "moderately price-sensitive"
    assert "elasticity" not in p and "-" not in p["price_change"]
    assert "15%" in p["limited_by"]


def test_hold_payload_drops_price_change():
    p = pricing_payload({**REC, "change_pct": 0.0, "revenue_change_pct": 0.0,
                         "recommended_price": 15.57}, 0.15)
    assert p["action"] == "hold" and "price_change" not in p and "revenue_change" not in p


def test_sensitivity_bands():
    assert sensitivity_band(-0.5) == "not very price-sensitive"
    assert sensitivity_band(-1.0) == "moderately price-sensitive"
    assert sensitivity_band(-1.5) == "moderately price-sensitive"
    assert sensitivity_band(-2.2) == "highly price-sensitive"


# ── guardrails ────────────────────────────────────────────────────────────────
GOOD = ("P013 is moderately price-sensitive, so cut its price by 13.9% from 15.57 to 13.40; "
        "weekly revenue should increase by 0.7%.")


def test_correct_sentence_passes():
    assert check_output(GOOD, P()) == (True, None)


def test_invented_number_rejected():
    ok, reason = check_output(GOOD + " Sales may double to 430 units.", P())
    assert not ok and reason.startswith("NUMBER")


def test_rerounded_number_rejected():
    ok, reason = check_output(GOOD.replace("13.9%", "14%"), P())
    assert not ok and reason.startswith("NUMBER")


def test_thousands_separator_and_trailing_zero_accepted():
    sp = segment_payload(SEG)
    text = ("High-value customers are 160 people, 16% of customers, who bring 40.1% of revenue; "
            "on average they bought on 1037 days and spent 58,087.23.")
    assert check_output(text, sp) == (True, None)


def test_contradicting_direction_rejected():
    ok, reason = check_output("Raise the price of P013 by 13.9% to 13.40.", P())
    assert not ok and reason.startswith("DIRECTION")


def test_missing_direction_rejected():
    ok, reason = check_output("P013 is moderately price-sensitive; the new price is 13.40.", P())
    assert not ok and reason.startswith("DIRECTION")


def test_length_and_jargon_rejected():
    assert check_output(GOOD + " x" * 300, P())[1].startswith("LENGTH")
    assert check_output(GOOD.replace("moderately price-sensitive", "beta -1.05 elastic"),
                        P())[1].startswith("JARGON")
    assert check_output("   ", P()) == (False, "EMPTY")


def test_fallbacks_always_pass_guardrails():
    for change, rev in [(0.149, 0.07), (-0.15, 0.2), (0.0, 0.0), (0.07, -0.05)]:
        p = pricing_payload({**REC, "change_pct": change, "revenue_change_pct": rev}, 0.15)
        assert check_output(fallback_text("pricing", p), p) == (True, None), p
    sp = segment_payload(SEG)
    assert check_output(fallback_text("segment", sp), sp) == (True, None)


# ── retry / fallback flow ─────────────────────────────────────────────────────
class Scripted(LLMClient):
    name = "scripted"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def generate(self, system_prompt, user_prompt):
        self.calls += 1
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _run(client):
    stats = RunStats()
    return explain_one(client, "pricing", P(), stats, sleep=lambda s: None), stats


def test_first_pass():
    res, st = _run(Scripted([GOOD]))
    assert res["source"] == "llm" and res["attempts"] == 1 and st.first_pass == 1


def test_bad_then_good_passes_on_retry():
    res, st = _run(Scripted(["Cut the price by 50%.", GOOD]))
    assert res["source"] == "llm" and res["attempts"] == 2 and st.passed_after_retry == 1
    assert "NUMBER" in res["rejection_reason"]


def test_bad_twice_falls_back():
    res, st = _run(Scripted(["Cut the price by 50%.", "Raise the price."]))
    assert res["source"] == "fallback" and st.fallback == 1
    assert res["explanation_text"] == fallback_text("pricing", P())


def test_api_error_falls_back_without_crashing():
    res, st = _run(Scripted([LLMError("429 quota"), LLMError("timeout")]))
    assert res["source"] == "fallback" and "API_ERROR" in res["rejection_reason"]


def test_mock_client_output_passes_guardrails():
    out = MockLLMClient().generate(SYSTEM_PROMPT, build_prompt("pricing", P()))
    assert check_output(out, P()) == (True, None)


# ── isolation ─────────────────────────────────────────────────────────────────
def test_explanations_never_touch_ground_truth():
    forbidden = re.compile(r"revenue_management_gt|true_elasticity|true_segment|gt_\w+")
    for f in (PIPELINE_ROOT / "explanations").glob("*.py"):
        hits = forbidden.findall(f.read_text(encoding="utf-8"))
        assert not hits, f"{f.name} references ground truth: {set(hits)}"
