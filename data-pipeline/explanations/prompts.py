"""
Prompts — Phase 9.

The system prompt carries the hard rules; each user prompt carries one JSON
payload (payloads.py). The guardrails (guardrails.py) then CHECK that the rules
were followed — the prompt asks, the guardrails enforce.
"""

from __future__ import annotations

import json

SYSTEM_PROMPT = """You write short explanations for a retail store manager.
You are given one JSON object of results that have already been calculated and validated.

Rules:
1. Use ONLY numbers that appear in the JSON, written exactly as they appear there (you may drop a trailing ".0"). Never calculate, convert, round differently, estimate, or add new numbers.
2. Do not mention any field that is missing from the JSON.
3. Do not add advice, predictions or reasons that are not in the JSON.
4. Plain English, 1 or 2 sentences, at most 60 words. No jargon (never say "elasticity", "coefficient", "beta" or "log-log"). No currency symbols, no bullet points, no markdown.
5. Describe price sensitivity using the exact wording in the "price_sensitivity" field."""

PRICING_TEMPLATE = """Explain this price recommendation for one product.
"action" says whether to raise, cut or hold the price; "price_change" is the size of that change; "revenue_direction" and "revenue_change" describe the expected weekly revenue effect; "limited_by" says what stopped the recommendation going further.

JSON:
{payload}"""

SEGMENT_TEMPLATE = """Describe this customer segment in plain English for a store manager: how big it is, how much of revenue it brings, and how often and how much its customers buy.

JSON:
{payload}"""


def payload_json(payload: dict) -> str:
    """Canonical JSON (sorted keys) — also what the cache hash is computed on."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def build_prompt(entity_type: str, payload: dict) -> str:
    template = PRICING_TEMPLATE if entity_type == "pricing" else SEGMENT_TEMPLATE
    return template.format(payload=json.dumps(payload, indent=2, ensure_ascii=False))
