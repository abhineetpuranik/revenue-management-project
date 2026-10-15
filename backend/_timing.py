"""Timing check after warm-up — deleted after use."""
import urllib.request, time, json

BASE = "http://localhost:5000"

def hit(path, n=3):
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        with urllib.request.urlopen(BASE + path) as r:
            r.read()
        times.append((time.perf_counter() - t0) * 1000)
    avg = sum(times) / len(times)
    print(f"  {avg:6.0f} ms avg ({min(times):.0f}-{max(times):.0f} ms range)  {path}")

print("Warm-up run:")
hit("/api/pricing/P001")

print("\nTimed runs (3 requests each):")
hit("/api/pricing/P001")
hit("/api/pricing/recommendations")
hit("/api/pricing/P001/explanation")
hit("/api/segments/high_value/explanation")
