"""Diagnose the 2s delay — deleted after use."""
import sys, time
sys.path.insert(0, r'd:\Projects\Revenue Management\backend')
sys.path.insert(0, r'd:\Projects\Revenue Management\data-pipeline')

from etl.db_connection import get_engine
from sqlalchemy import text

engine = get_engine()

# Time a direct DB query
for i in range(3):
    t0 = time.perf_counter()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM pricing_recommendation WHERE product_id='P001'")).fetchall()
    print(f"  Direct DB query {i+1}: {(time.perf_counter()-t0)*1000:.0f} ms  ({len(rows)} rows)")

# Time a socket connect to localhost:5000
import socket
for i in range(3):
    t0 = time.perf_counter()
    s = socket.create_connection(("localhost", 5000), timeout=5)
    s.close()
    print(f"  Socket connect {i+1}: {(time.perf_counter()-t0)*1000:.0f} ms")
