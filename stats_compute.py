#!/usr/bin/env python3
"""Reproducible statistics for the MCP User-Controllability Study.

Every number in stats_summary.md comes from THIS script over classifications.jsonl.
Run: python3 stats_compute.py [classifications file] [review overrides file]

Normalization (schema drift in 12 of 1,347 rows, evidence reviewed Jul 14 2026):
- attribution "per_user" (2 rows) -> per_user_agent_attribution (evidence shows
  per-user API attribution / single-user-by-design).
- revocability "expiring" (1 row) -> insufficient_data (evidence: test keys expire,
  no revocation path documented for production keys; conservative).
- consent_surface "user_mediated" (9 rows) -> kept as its own bucket
  per_action_human_approval (rubric extension: evidence shows per-action human
  approval, a consent surface stronger than connection-time; NOT "none").

Denominator policy: every stat states its numerator/denominator explicitly.
"auth-required" = credential_delivery in {env_var_static_key, config_file,
oauth_redirect, user_mediated} (a real credential channel is documented).
insufficient_data rows never count toward a "has/lacks X" claim.
"""

import json
import sys
from collections import Counter

_DATA_FILE = sys.argv[1] if len(sys.argv) > 1 else "classifications.jsonl"
ROWS = [json.loads(l) for l in open(_DATA_FILE)]

# Optional second arg: an evidence-reviewed override file (one JSON per line:
# {"repo","dimension","reviewed_label",...}). Same spirit as REMAP below: manual
# re-read of the README, label corrected, evidence quoted. Raw classifications are
# never hand-edited; overrides are applied here so every number stays reproducible.
# Sep 15 2026: review-consent-2026-09-15.jsonl (30 agent_reachable_consent rows +
# 1 user_chosen_duration row re-read; 19 labels changed).
_REVIEW_FILE = sys.argv[2] if len(sys.argv) > 2 else None
OVERRIDES = {}
if _REVIEW_FILE:
    for _l in open(_REVIEW_FILE):
        if _l.strip():
            _o = json.loads(_l)
            OVERRIDES[(_o["repo"], _o["dimension"])] = _o["reviewed_label"]

REMAP = {
    "attribution": {"per_user": "per_user_agent_attribution"},
    "revocability": {"expiring": "insufficient_data"},
    "consent_surface": {"user_mediated": "per_action_human_approval"},
}

def lab(r, dim):
    v = OVERRIDES.get((r["repo"], dim), r[dim]["label"])
    return REMAP.get(dim, {}).get(v, v)

DIMS = ["credential_delivery", "scoping_granularity", "revocability",
        "credential_lifetime", "consent_surface", "attribution"]

AUTH_CHANNELS = {"env_var_static_key", "config_file", "oauth_redirect", "user_mediated"}
NO_REVOKE = {"none", "shared_key_rotation_only", "redeploy_only"}

def pct(n, d):
    return f"{n}/{d} = {100*n/d:.1f}%"

def main():
    n_all = len(ROWS)
    auth = [r for r in ROWS if lab(r, "credential_delivery") in AUTH_CHANNELS]
    n_auth = len(auth)
    print(f"rows: {n_all}   auth-required: {pct(n_auth, n_all)}\n")

    for dim in DIMS:
        c = Counter(lab(r, dim) for r in ROWS)
        print(f"{dim} (all rows):")
        for k, v in c.most_common():
            print(f"  {k}: {v} ({100*v/n_all:.1f}%)")
        print()

    print("=== HEADLINES (each with explicit numerator/denominator) ===")

    ad = Counter(lab(r, "credential_delivery") for r in auth)
    autom = ad["env_var_static_key"] + ad["config_file"]
    print(f"H1 automated credential pipe, of auth-required: {pct(autom, n_auth)}")
    print(f"   oauth_redirect of auth-required: {pct(ad['oauth_redirect'], n_auth)}")
    print(f"   user_mediated of auth-required: {pct(ad['user_mediated'], n_auth)}")

    cs = Counter(lab(r, "consent_surface") for r in ROWS)
    cs_auth = Counter(lab(r, "consent_surface") for r in auth)
    print(f"H2 no consent surface, of ALL servers: {pct(cs['none'], n_all)}")
    print(f"   no consent surface, of auth-required: {pct(cs_auth['none'], n_auth)}")
    print(f"   agent-reachable consent, of ALL: {pct(cs['agent_reachable_consent'], n_all)}")
    print(f"   per-action human approval (rubric ext), of ALL: {pct(cs['per_action_human_approval'], n_all)}")

    rv_auth = Counter(lab(r, "revocability") for r in auth)
    norev = sum(rv_auth[k] for k in NO_REVOKE)
    print(f"H3 no individual revocation path, of auth-required: {pct(norev, n_auth)}")
    print(f"   documented individual revocation, of auth-required: {pct(rv_auth['documented_revocation'], n_auth)}")

    lt_auth = Counter(lab(r, "credential_lifetime") for r in auth)
    print(f"H4 long-lived static credential, of auth-required: {pct(lt_auth['long_lived_static'], n_auth)}")
    print(f"   user-chosen duration, of auth-required: {lt_auth['user_chosen_duration']} (zero)")

    sc_auth = Counter(lab(r, "scoping_granularity") for r in auth)
    sc_doc = n_auth - sc_auth["insufficient_data"] - sc_auth["none"]
    granular = sc_auth["user_selected_scope"] + sc_auth["per_action"] + sc_auth["per_tool"] + sc_auth["per_user"]
    print(f"H5 all-or-nothing, of auth-required: {pct(sc_auth['all_or_nothing'], n_auth)}")
    print(f"   all-or-nothing, of auth-required WITH documented scoping: {pct(sc_auth['all_or_nothing'], sc_doc)}")
    print(f"   any user-selectable narrowing, of auth-required: {pct(granular, n_auth)}")

    at = Counter(lab(r, "attribution") for r in ROWS)
    det = at["shared_identity"] + at["per_user_agent_attribution"]
    print(f"H6 shared identity, of servers with determinable attribution: {pct(at['shared_identity'], det)}")

    def worst(r):
        return (lab(r, "credential_delivery") in ("env_var_static_key", "config_file")
                and lab(r, "scoping_granularity") == "all_or_nothing"
                and lab(r, "revocability") in NO_REVOKE
                and lab(r, "credential_lifetime") == "long_lived_static"
                and lab(r, "consent_surface") == "none"
                and lab(r, "attribution") == "shared_identity")
    w = [r for r in ROWS if worst(r)]
    print(f"H7 composite zero-controllability (affirmative worst label on ALL 6 dims):")
    print(f"   {pct(len(w), n_all)} of all; {pct(len(w), n_auth)} of auth-required")

    vs = json.load(open("verification_sample.json"))
    agree = sum(d["agreements"] for d in vs["details"])
    tot = sum(d["total"] for d in vs["details"])
    print(f"\nverification sample: {pct(agree, tot)} cell agreement over {vs['sampled']} repos; "
          f"full-agreement repos {sum(1 for d in vs['details'] if d['agreements']==d['total'])}/{vs['sampled']}")
    dis, per_tot = Counter(), Counter()
    for d in vs["details"]:
        for dim, cell in d["per_dim"].items():
            per_tot[dim] += 1
            if not cell["agree"]:
                dis[dim] += 1
    for dim in DIMS:
        print(f"  {dim}: {100*dis[dim]/per_tot[dim]:.1f}% disagreement")

if __name__ == "__main__":
    main()
