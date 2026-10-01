#!/usr/bin/env python3
"""Export the study's aggregate distributions to CSV (the public reproducibility artifact).
Reuses stats_compute.py's normalization + overrides so the numbers match the post exactly.
Run: python3 export_aggregates.py classifications-2026-09-15.jsonl review-consent-2026-09-15.jsonl > aggregates-2026-09-15.csv
Per-repository labels are deliberately NOT exported here (no name-and-shame; available to researchers on request)."""
import sys, csv, io, contextlib, importlib.util
from collections import Counter
spec = importlib.util.spec_from_file_location("sc", "stats_compute.py")
sc = importlib.util.module_from_spec(spec)
_argv = sys.argv[:]
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(sc)   # runs stats_compute with the same argv; captures its printout
rows = sc.ROWS
w = csv.writer(sys.stdout)
w.writerow(["dimension","label","count","share_of_all_rows","rows_total"])
n = len(rows)
for d in sc.DIMS:
    c = Counter(sc.lab(r, d) for r in rows)   # identical normalization + overrides as the headline script
    for k, v in c.most_common():
        w.writerow([d, k, v, f"{100*v/n:.1f}%", n])
