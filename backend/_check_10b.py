"""Curl-equivalent check for Phase 10b endpoints — deleted after use."""
import json, time, urllib.request, urllib.error

BASE = "http://localhost:5000"
TIMINGS = {}


def get(path, label=None):
    url = BASE + path
    tag = f"[{label}]" if label else ""
    print(f"\n{'='*62}\n  GET {path}  {tag}\n{'='*62}")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url) as r:
            body = r.read().decode()
            elapsed = time.perf_counter() - t0
            data = json.loads(body)
            print(f"  HTTP 200  ({elapsed*1000:.0f} ms)")
            print(json.dumps(data, indent=2)[:900])
            TIMINGS[path] = elapsed
            return data, 200
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        body = e.read().decode()
        data = json.loads(body) if body else {}
        print(f"  HTTP {e.code}  ({elapsed*1000:.0f} ms)")
        print(json.dumps(data, indent=2))
        TIMINGS[path] = elapsed
        return data, e.code


# ── Pricing single product ────────────────────────────────────────────────
get("/api/pricing/P001")
get("/api/pricing/P027", label="CURRENT_PRICE_BREAKS_MARGIN")
get("/api/pricing/P006", label="PRICE_RANGE binding — hold")
get("/api/pricing/ZZZZ", label="unknown -> 404")

# ── Pricing list ──────────────────────────────────────────────────────────
d, _ = get("/api/pricing/recommendations")
print(f"\n  [summary] total={d['total']} page={d['page']} page_size={d['page_size']} pages={d['pages']}")
print(f"  First item keys: {list(d['recommendations'][0].keys())}")

d, _ = get("/api/pricing/recommendations?category=Electronics")
print(f"\n  [summary] Electronics only: total={d['total']}")

d, _ = get("/api/pricing/recommendations?category=Nonexistent")
print(f"\n  [summary] Unknown category: total={d['total']}")

get("/api/pricing/recommendations?page=0", label="bad page -> 400")
get("/api/pricing/recommendations?page_size=abc", label="bad page_size -> 400")
get("/api/pricing/recommendations?page_size=9999", label="page_size too large -> 400")

# ── Explanation endpoints ─────────────────────────────────────────────────
d, _ = get("/api/pricing/P001/explanation")
print(f"\n  [summary] available={d['explanation_available']}  source={d.get('source')}  text_len={len(d.get('explanation','') or '')}")
print(f"  explanation: {d.get('explanation','')[:120]}")
print(f"  payload keys: {list((d.get('payload') or {}).keys())}")

d, _ = get("/api/pricing/P027/explanation")
print(f"\n  [P027 explanation] available={d['explanation_available']}")

get("/api/pricing/ZZZZ/explanation", label="unknown product -> 404")

d, _ = get("/api/forecast/P001/explanation", label="forecast explanation (unsupported)")
print(f"\n  [summary] available={d['explanation_available']}  reason={d.get('unavailable_reason','')[:80]}")

get("/api/forecast/ZZZZ/explanation", label="unknown product -> 404")

d, _ = get("/api/segments/high_value/explanation")
print(f"\n  [segment explanation] available={d['explanation_available']}  source={d.get('source')}")
print(f"  text: {d.get('explanation','')[:120]}")

get("/api/segments/vip/explanation", label="unknown segment -> 404")

# ── Timing summary ────────────────────────────────────────────────────────
print("\n" + "="*62)
print("  RESPONSE TIMES")
print("="*62)
for path, t in sorted(TIMINGS.items(), key=lambda x: -x[1]):
    print(f"  {t*1000:7.1f} ms  {path}")
