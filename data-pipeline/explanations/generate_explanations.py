"""
Phase 9 orchestrator — LLM explanation layer (batch).

Steps
-----
1. Read validated outputs: pricing_recommendation (Phase 8b) and
   segment_summary (Phase 6) — application schema only, never ground truth.
2. Build one payload per product and per segment (payloads.py).
3. Cache: if an entity's payload hash and model are unchanged since the last
   run and its stored text came from the LLM, reuse it (no API call).
4. Otherwise call the LLM → guardrails → on rejection or API error retry once
   → if still failing, use the template fallback. Every entity always ends up
   with an explanation; nothing crashes the batch.
5. Save to llm_explanation (MySQL, delete-and-reload in one transaction) and
   data/explanations/llm_explanations.csv.

Run
---
    cd data-pipeline
    LLM_PROVIDER=mock   python -m explanations.generate_explanations   # offline
    LLM_PROVIDER=gemini python -m explanations.generate_explanations   # needs LLM_API_KEY

Public interface (Phase 10b)
----------------------------
    from explanations.generate_explanations import get_explanation
    get_explanation("pricing", "P001")   /   get_explanation("segment", "high_value")
"""

from __future__ import annotations

import hashlib
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_engine
from explanations.explanation_config import MAX_RETRIES, RETRY_BACKOFF_S
from explanations.fallback import fallback_text
from explanations.guardrails import check_output
from explanations.llm_client import LLMClient, LLMError, get_client
from explanations.payloads import build_all_payloads
from explanations.prompts import SYSTEM_PROMPT, build_prompt, payload_json

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

TABLE_NAME = "llm_explanation"
OUTPUT_DIR = _PIPELINE_ROOT / "data" / "explanations"
CSV_PATH = OUTPUT_DIR / "llm_explanations.csv"

OUTPUT_COLUMNS = ["explanation_id", "entity_type", "entity_id", "explanation_text", "source",
                  "payload_json", "payload_hash", "model_name", "guardrail_status",
                  "rejection_reason", "attempts", "generated_at"]

# Kept identical to database/schema.sql (section 4d).
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_explanation (
    explanation_id    INT            NOT NULL,
    entity_type       VARCHAR(10)    NOT NULL,
    entity_id         VARCHAR(20)    NOT NULL,
    explanation_text  VARCHAR(1000)  NOT NULL,
    source            VARCHAR(10)    NOT NULL,
    payload_json      TEXT           NOT NULL,
    payload_hash      CHAR(64)       NOT NULL,
    model_name        VARCHAR(60)    NOT NULL,
    guardrail_status  VARCHAR(10)    NOT NULL,
    rejection_reason  VARCHAR(255)   NOT NULL DEFAULT '',
    attempts          INT            NOT NULL,
    generated_at      DATETIME       NOT NULL,
    CONSTRAINT pk_llm_explanation PRIMARY KEY (explanation_id),
    CONSTRAINT uq_llm_explanation_entity UNIQUE (entity_type, entity_id)
) ENGINE=InnoDB
"""


@dataclass
class RunStats:
    first_pass: int = 0
    passed_after_retry: int = 0
    fallback: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    rejections: list = field(default_factory=list)


def _hash(pj: str) -> str:
    return hashlib.sha256(pj.encode("utf-8")).hexdigest()


def explain_one(client: LLMClient, entity_type: str, payload: dict, stats: RunStats,
                sleep=time.sleep) -> dict:
    """LLM → guardrails → retry once → fallback. Returns text, source, status, reason, attempts."""
    prompt = build_prompt(entity_type, payload)
    reasons = []
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            stats.api_calls += 1
            out = client.generate(SYSTEM_PROMPT, prompt)
        except LLMError as exc:
            reasons.append(f"API_ERROR: {exc}"[:120])
            if attempt <= MAX_RETRIES:
                sleep(RETRY_BACKOFF_S)
            continue
        ok, reason = check_output(out, payload)
        if ok:
            if attempt == 1:
                stats.first_pass += 1
            else:
                stats.passed_after_retry += 1
            return {"explanation_text": out.strip(), "source": "llm", "guardrail_status": "passed",
                    "rejection_reason": "; ".join(reasons), "attempts": attempt}
        reasons.append(reason)
        stats.rejections.append(reason)
    stats.fallback += 1
    return {"explanation_text": fallback_text(entity_type, payload), "source": "fallback",
            "guardrail_status": "fallback", "rejection_reason": "; ".join(reasons)[:255],
            "attempts": MAX_RETRIES + 1}


def _load_inputs(engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    with engine.connect() as conn:
        recs = pd.read_sql(text("SELECT * FROM pricing_recommendation ORDER BY product_id"), conn)
        segs = pd.read_sql(text("SELECT * FROM segment_summary"), conn)
    if recs.empty or segs.empty:
        raise RuntimeError("pricing_recommendation or segment_summary is empty — run Phase 8b "
                           "(pricing.run_pricing) and Phase 6 (segmentation.run_segmentation) first.")
    return recs, segs


def _load_cache(engine) -> dict:
    """{(entity_type, entity_id): row} from the previous run, or {} if none."""
    try:
        with engine.connect() as conn:
            prev = pd.read_sql(text(f"SELECT * FROM {TABLE_NAME}"), conn)
    except Exception:            # table does not exist yet
        return {}
    return {(r["entity_type"], r["entity_id"]): r for r in prev.to_dict(orient="records")}


def generate(engine, client: LLMClient, sleep=time.sleep) -> tuple[pd.DataFrame, RunStats]:
    from pricing.pricing_config import MAX_PRICE_CHANGE_PCT
    recs, segs = _load_inputs(engine)
    items = build_all_payloads(recs, segs, MAX_PRICE_CHANGE_PCT)
    cache = _load_cache(engine)
    stats = RunStats()
    now = datetime.now().replace(microsecond=0)
    rows = []
    for i, (etype, eid, payload) in enumerate(items, start=1):
        pj = payload_json(payload)
        h = _hash(pj)
        prev = cache.get((etype, eid))
        if (prev is not None and prev["payload_hash"] == h and prev["source"] == "llm"
                and prev["model_name"] == client.name):
            stats.cache_hits += 1
            res = {k: prev[k] for k in ["explanation_text", "source", "guardrail_status",
                                        "rejection_reason", "attempts", "generated_at"]}
        else:
            res = explain_one(client, etype, payload, stats, sleep=sleep)
            res["generated_at"] = now
        rows.append({"explanation_id": i, "entity_type": etype, "entity_id": eid,
                     "payload_json": pj, "payload_hash": h, "model_name": client.name, **res})
    df = pd.DataFrame(rows)[OUTPUT_COLUMNS]
    df["rejection_reason"] = df["rejection_reason"].fillna("")
    return df, stats


def save(df: pd.DataFrame, engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        conn.execute(text(f"DELETE FROM {TABLE_NAME}"))
        df.to_sql(TABLE_NAME, conn, if_exists="append", index=False, method="multi")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)
    logger.info("Saved %d explanations to %s and %s", len(df), TABLE_NAME, CSV_PATH)


def get_explanation(entity_type: str, entity_id: str, engine=None) -> dict:
    engine = engine or get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(f"SELECT * FROM {TABLE_NAME} WHERE entity_type = :t AND entity_id = :i"),
                         conn, params={"t": entity_type, "i": entity_id})
    if df.empty:
        raise KeyError(f"No explanation for {entity_type}/{entity_id}. "
                       "Run python -m explanations.generate_explanations first.")
    return df.iloc[0].to_dict()


def _section(title: str) -> None:
    print(f"\n{'=' * 66}\n  {title}\n{'=' * 66}")


def main() -> None:
    t0 = time.time()
    _section("Phase 9 -- LLM explanation layer")
    engine = get_engine()
    client = get_client()
    print(f"  Provider / model : {client.name}")

    df, stats = generate(engine, client)

    _section("Run summary")
    n = len(df)
    print(f"  Explanations      : {n}  (pricing {int((df['entity_type'] == 'pricing').sum())}, "
          f"segment {int((df['entity_type'] == 'segment').sum())})")
    print(f"  Reused from cache : {stats.cache_hits}")
    print(f"  Passed first time : {stats.first_pass}")
    print(f"  Passed on retry   : {stats.passed_after_retry}")
    print(f"  Template fallback : {stats.fallback}")
    print(f"  LLM calls made    : {stats.api_calls}")
    if stats.rejections:
        print("\n  Guardrail rejections")
        print(pd.Series(stats.rejections).str.split(":").str[0].value_counts().to_string())

    _section("Samples")
    for _, r in pd.concat([df[df["entity_type"] == "pricing"].head(4),
                           df[df["entity_type"] == "segment"].head(2)]).iterrows():
        print(f"\n  [{r['entity_type']}/{r['entity_id']}] ({r['source']})")
        print(f"  payload: {r['payload_json']}")
        print(f"  text   : {r['explanation_text']}")

    _section("Saving")
    save(df, engine)
    _section(f"Phase 9 complete ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
