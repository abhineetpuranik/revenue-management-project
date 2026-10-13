from __future__ import annotations

import re

from explanations.explanation_config import BANNED_TERMS, MAX_CHARS

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

_UP = r"\b(rais\w*|increas\w*|higher|up)\b"
_DOWN = r"\b(cut\w*|lower\w*|reduc\w*|decreas\w*|drop\w*)"
_HOLD = r"\b(keep\w*|hold\w*|unchanged|maintain\w*|stay\w*|same)"


def numbers_in(text: str) -> list[float]:
    vals = []
    for tok in _NUM.findall(text):
        tok = tok.rstrip(",").replace(",", "")
        try:
            vals.append(float(tok))
        except ValueError:
            continue
    return vals


def allowed_numbers(payload: dict) -> set[float]:
    allowed: set[float] = set()
    for v in payload.values():
        allowed.update(numbers_in(str(v)))
    return allowed


def check_numbers(text: str, payload: dict):
    allowed = allowed_numbers(payload)
    bad = [n for n in numbers_in(text) if not any(abs(n - a) < 1e-9 for a in allowed)]
    return (False, f"NUMBER: {bad} not in payload") if bad else (True, None)


def check_direction(text: str, payload: dict):
    action = payload.get("action")
    if action is None:
        return True, None
    t = text.lower()
    price_down = re.search(rf"{_DOWN}\s+(?:the\s+|its\s+|this\s+)?price|price\s+{_DOWN}|price\s+(?:cut|reduction|drop)", t)
    price_up = re.search(rf"{_UP}\s+(?:the\s+|its\s+|this\s+)?price|price\s+{_UP}|price\s+(?:rise|increase|hike)", t)
    if action == "raise":
        if price_down:
            return False, "DIRECTION: says cut, action is raise"
        if not re.search(_UP, t):
            return False, "DIRECTION: never says raise"
    elif action == "cut":
        if price_up:
            return False, "DIRECTION: says raise, action is cut"
        if not re.search(_DOWN, t):
            return False, "DIRECTION: never says cut"
    elif action == "hold":
        if price_up or price_down:
            return False, "DIRECTION: suggests a price change, action is hold"
        if not re.search(_HOLD, t):
            return False, "DIRECTION: never says keep the price"
    return True, None


def check_length(text: str, max_chars: int = MAX_CHARS):
    return (len(text) <= max_chars, None if len(text) <= max_chars else f"LENGTH: {len(text)} chars")


def check_jargon(text: str):
    t = text.lower()
    hits = [w for w in BANNED_TERMS if w.lower() in t]
    return (False, f"JARGON: {hits}") if hits else (True, None)


def check_output(text: str | None, payload: dict):
    if not text or not text.strip():
        return False, "EMPTY"
    text = text.strip()
    for check in (check_length(text), check_jargon(text), check_numbers(text, payload),
                  check_direction(text, payload)):
        if not check[0]:
            return check
    return True, None
