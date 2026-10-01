#!/usr/bin/env python3
"""Cell-level comparison of two classification files over the repos they share.
Run: python3 compare_runs.py A.jsonl B.jsonl [--split]
Prints per-dimension and overall agreement, the top label transitions, and (with --split)
agreement broken out by cohort (July vs Sep additions) and README length (<= the old slice
cap vs longer), which separates truncation effects from model/rubric/run-to-run effects.
No overrides or remaps are applied: this compares raw labels."""
import json, sys
from collections import Counter
DIMS = ["credential_delivery", "scoping_granularity", "revocability",
        "credential_lifetime", "consent_surface", "attribution"]
def load(p): return {json.loads(l)["repo"]: json.loads(l) for l in open(p) if l.strip()}
a, b = load(sys.argv[1]), load(sys.argv[2])
repos = sorted(set(a) & set(b))
print(f"A={sys.argv[1]} ({len(a)} rows)  B={sys.argv[2]} ({len(b)} rows)  shared={len(repos)}")
def agree(sel):
    per = {d: sum(a[r][d]["label"] == b[r][d]["label"] for r in sel) for d in DIMS}
    return per, sum(per.values())
per, tot = agree(repos)
for d in DIMS:
    print(f"  {d}: {per[d]}/{len(repos)} = {100*per[d]/len(repos):.1f}% same")
    c = Counter((a[r][d]["label"], b[r][d]["label"]) for r in repos if a[r][d]["label"] != b[r][d]["label"])
    for (x, y), v in c.most_common(4):
        print(f"      {x} -> {y}: {v}")
print(f"  OVERALL: {tot}/{len(repos)*6} = {100*tot/(len(repos)*6):.1f}% of cells same")
if "--split" in sys.argv:
    adds = {l.strip() for l in open("frame-additions-2026-09-10.txt") if l.strip()}
    def rl(repo): return len(json.load(open("corpus/" + repo.replace("/", "__") + ".json")).get("readme", "") or "")
    L = {r: rl(r) for r in repos}
    for name, grp, cap in (("july", [r for r in repos if r not in adds], 3500), ("additions", [r for r in repos if r in adds], 4000)):
        for lab, sel in ((f"README<={cap} (identical input to the sliced run)", [r for r in grp if L[r] <= cap]),
                         (f"README>{cap} (sliced before)", [r for r in grp if L[r] > cap])):
            if not sel: continue
            per, tot = agree(sel)
            print(f"  {name} | {lab} n={len(sel)}: overall {100*tot/(len(sel)*6):.1f}%  per-dim " +
                  " ".join(f"{100*per[d]/len(sel):.0f}" for d in DIMS))
