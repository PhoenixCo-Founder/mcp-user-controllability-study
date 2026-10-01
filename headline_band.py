#!/usr/bin/env python3
"""Headline statistics in "what the README documents" form, with a run-to-run band.

Run: python3 headline_band.py
Inputs (all in this directory):
  classifications-2026-09-15.jsonl + review-consent-2026-09-15.jsonl   (committed Sep 15 dataset:
      first 3,500/4,000 README chars, two rubric texts, mixed models)
  classifications-full-readme-2026-09-30-v2.jsonl                      (v2: full README <=30,000 chars,
      July detailed rubric for every row, claude-sonnet-5-5 pinned)
  classifications-full-readme-2026-09-30-v2-repeat200.jsonl            (same instrument as v2, second
      independent pass over a seeded 200-repo random sample)

Why this exists (Sep 30 2026): the same rubric gives 85.8% cell-level run-to-run agreement, and
most flips are label <-> insufficient_data. A stat that counts only an affirmative "worst" label
(e.g. "no revocation path") therefore swings with how readily the classifier infers from silence.
Each headline is printed two ways:
  affirmative  = rows carrying the label itself
  not documented = everything except the affirmative positive capability (the complement)
and for the 200-repo sample both passes are shown so the band is visible.
Normalization (REMAP, overrides) is imported from stats_compute.py so numbers cannot drift.
"""
import json
import sys
from collections import Counter

sys.argv = [sys.argv[0]]  # stats_compute reads argv at import; keep it on its default file
import stats_compute as sc

AUTH = sc.AUTH_CHANNELS
NO_REVOKE = sc.NO_REVOKE
NARROW = {"user_selected_scope", "per_action", "per_tool", "per_user"}


def load(path, review=None):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    ov = {}
    if review:
        for l in open(review):
            if l.strip():
                o = json.loads(l)
                ov[(o["repo"], o["dimension"])] = o["reviewed_label"]

    def lab(r, dim):
        v = ov.get((r["repo"], dim), r[dim]["label"])
        return sc.REMAP.get(dim, {}).get(v, v)

    return [{"repo": r["repo"], **{d: lab(r, d) for d in sc.DIMS}} for r in rows]


def heads(rows):
    n = len(rows)
    auth = [r for r in rows if r["credential_delivery"] in AUTH]
    na = len(auth)
    c = lambda dim, labels, sel=auth: sum(r[dim] in labels for r in sel)
    out = {}

    def put(k, v):
        assert k not in out, f'duplicate stat key: {k}'
        out[k] = v
    put("rows", (n, n))
    put("auth-required (documents a credential channel), of all", (na, n))
    put("H1 credential arrives by env var or config file, of auth", (c("credential_delivery", {"env_var_static_key", "config_file"}), na))
    put("   user-mediated delivery, of auth", (c("credential_delivery", {"user_mediated"}), na))
    put("   OAuth redirect, of auth", (c("credential_delivery", {"oauth_redirect"}), na))
    put("H2 no consent surface (affirmative), of all", (c("consent_surface", {"none"}, rows), n))
    put("   no consent surface (affirmative), of auth", (c("consent_surface", {"none"}), na))
    put("   documents ANY consent surface, of auth", (c("consent_surface", {"connection_time_approval", "per_action_human_approval", "agent_reachable_consent"}), na))
    put("H3 documents a way to revoke one grant, of auth", (c("revocability", {"documented_revocation"}), na))
    put("   does NOT document a single-grant revocation (complement), of auth", (na - c("revocability", {"documented_revocation"}), na))
    put("   affirmative no-individual-revocation label, of auth", (c("revocability", NO_REVOKE), na))
    put("H4 documents an expiring or user-chosen lifetime, of auth", (c("credential_lifetime", {"expiring", "user_chosen_duration"}), na))
    put("   does NOT document an expiring lifetime (complement), of auth", (na - c("credential_lifetime", {"expiring", "user_chosen_duration"}), na))
    put("   affirmative long-lived static label, of auth", (c("credential_lifetime", {"long_lived_static"}), na))
    put("   user-chosen duration, of auth", (c("credential_lifetime", {"user_chosen_duration"}), na))
    put("H5 documents any narrowing of what the agent gets, of auth", (c("scoping_granularity", NARROW), na))
    put("   does NOT document any (complement), of auth", (na - c("scoping_granularity", NARROW), na))
    put("   affirmative all-or-nothing label, of auth", (c("scoping_granularity", {"all_or_nothing"}), na))
    put("H6 documents per-user/per-agent attribution, of auth", (c("attribution", {"per_user_agent_attribution"}), na))
    put("   does NOT document it (complement), of auth", (na - c("attribution", {"per_user_agent_attribution"}), na))
    put("   affirmative shared-identity label, of auth", (c("attribution", {"shared_identity"}), na))
    worst = [r for r in auth if r["credential_delivery"] in ("env_var_static_key", "config_file")
             and r["scoping_granularity"] == "all_or_nothing" and r["revocability"] in NO_REVOKE
             and r["credential_lifetime"] == "long_lived_static" and r["consent_surface"] == "none"
             and r["attribution"] == "shared_identity"]
    put("H7 affirmative worst label on all six, of auth", (len(worst), na))
    nopos = [r for r in auth if r["credential_delivery"] in ("env_var_static_key", "config_file")
             and r["scoping_granularity"] not in NARROW and r["revocability"] != "documented_revocation"
             and r["credential_lifetime"] not in ("expiring", "user_chosen_duration")
             and r["consent_surface"] not in ("connection_time_approval", "per_action_human_approval", "agent_reachable_consent")
             and r["attribution"] != "per_user_agent_attribution"]
    put("H7b documents NONE of the five user controls + automated delivery, of auth", (len(nopos), na))
    return out


def fmt(t):
    a, b = t
    return f"{a}/{b} = {100*a/b:.1f}%" if b else "n/a"


def main():
    committed = load("classifications-2026-09-15.jsonl", "review-consent-2026-09-15.jsonl")
    v2 = load("classifications-full-readme-2026-09-30-v2.jsonl")
    rep = load("classifications-full-readme-2026-09-30-v2-repeat200.jsonl")
    sample = {r["repo"] for r in rep}
    v2s = [r for r in v2 if r["repo"] in sample]
    cs = [r for r in committed if r["repo"] in sample]
    hc, hv, ha, hb, hcs = heads(committed), heads(v2), heads(v2s), heads(rep), heads(cs)
    print("FULL FRAME (1,634 repos)")
    print(f"{'stat':72} | {'committed Sep 15':20} | {'v2 full README':20}")
    for k in hc:
        print(f"{k:72} | {fmt(hc[k]):20} | {fmt(hv[k]):20}")
    print("\nRUN-TO-RUN BAND on the seeded 200-repo sample (same instrument, two independent passes)")
    print(f"{'stat':72} | {'v2 pass A':18} | {'v2 pass B':18} | {'A-B pts':8} | {'committed, same 200':18}")
    for k in ha:
        a, b = ha[k], hb[k]
        d = (100 * a[0] / a[1] - 100 * b[0] / b[1]) if a[1] and b[1] else 0
        print(f"{k:72} | {fmt(a):18} | {fmt(b):18} | {d:+8.1f} | {fmt(hcs[k]):18}")
    print("\nPER-LABEL PERSISTENCE on the 200 sample (of repos labeled X in pass A, share labeled X in pass B)")
    A = {r["repo"]: r for r in v2s}
    B = {r["repo"]: r for r in rep}
    for dim in sc.DIMS:
        ca = Counter(A[r][dim] for r in A)
        parts = []
        for labl, n in ca.most_common():
            keep = sum(1 for r in A if A[r][dim] == labl and B[r][dim] == labl)
            parts.append(f"{labl} {keep}/{n}")
        print(f"  {dim}: " + "; ".join(parts))


if __name__ == "__main__":
    main()
