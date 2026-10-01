#!/usr/bin/env python3
"""Two mechanical checks on a classification file against the stored READMEs (corpus/*.json).
Run: python3 evidence_check.py classifications-full-readme-2026-09-30-v2.jsonl

1. Quote check: for every cell carrying a positive-capability label, does at least one quoted
   fragment (>= 12 chars, between quotes or backticks) of the evidence appear verbatim in the
   first 30,000 README chars (whitespace-normalized) or in the file list?
2. Keyword ceiling: among credential-requiring rows NOT labelled as documenting a capability, how
   many READMEs contain a keyword that could indicate the capability? Label + keyword hits is a
   generous upper bound on "documents X"; the label count alone is the reported figure.
No labels are changed by this script."""
import json, re, sys
from collections import Counter
import importlib
sys_argv = sys.argv[:]
sys.argv = [sys.argv[0]]
sc = importlib.import_module("stats_compute")
path = sys_argv[1]
rows = [json.loads(l) for l in open(path) if l.strip()]
CAP = 30000
def corpus(repo):
    d = json.load(open("corpus/" + repo.replace("/", "__") + ".json"))
    return (d.get("readme") or "")[:CAP], " ".join(map(str, d.get("files") or []))
norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
def frags(ev):
    out = re.findall(r"`([^`]{12,})`", ev) + re.findall(r"\"([^\"]{12,})\"", ev) + re.findall(r"'([^']{12,})'", ev) + re.findall(r"“([^”]{12,})”", ev)
    return [norm(f.replace("**", "").rstrip(".…")) for f in out]
POS = {"revocability": {"documented_revocation"}, "credential_lifetime": {"expiring", "user_chosen_duration"},
       "scoping_granularity": {"user_selected_scope", "per_action", "per_tool", "per_user"},
       "attribution": {"per_user_agent_attribution"},
       "consent_surface": {"connection_time_approval", "agent_reachable_consent"},
       "credential_delivery": {"env_var_static_key", "config_file", "oauth_redirect", "user_mediated"}}
print("QUOTE CHECK (positive-capability cells, all rows)")
for dim, labels in POS.items():
    tot = ok = noq = 0
    for r in rows:
        if r[dim]["label"] not in labels: continue
        tot += 1
        readme, files = corpus(r["repo"])
        hay = norm(readme.replace("**", "")) + " " + norm(files)
        fs = frags(r[dim].get("evidence") or "")
        if not fs: noq += 1; continue
        if any(f in hay or (len(f) > 40 and f[:40] in hay) for f in fs): ok += 1
    print(f"  {dim}: {ok}/{tot} cells have a verbatim-found quote; {noq} carry no quoted fragment; {tot-ok-noq} quoted but not found verbatim")
auth = [r for r in rows if r["credential_delivery"]["label"] in sc.AUTH_CHANNELS]
KW = {"revocability": (POS["revocability"], r"\brevok|\brevocation|\bdeauthori[sz]|\bdisconnect (the|your|an?) |remove (the )?(app|access|authori[sz]ation|grant)|delete (the|your|an?) (api )?(key|token)"),
      "credential_lifetime": (POS["credential_lifetime"], r"\bexpir|\bttl\b|refresh[_ ]token|short[- ]lived|\bvalid for\b"),
      "scoping_granularity": (POS["scoping_granularity"], r"\bscopes?\b|read[- ]only|\ballowlist|\bwhitelist|permission"),
      "attribution": (POS["attribution"], r"per[- ]user|multi[- ]tenant|audit log|per[- ]agent")}
print(f"\nKEYWORD CEILING (credential-requiring rows, n={len(auth)})")
for dim, (labels, pat) in KW.items():
    lab_n = sum(r[dim]["label"] in labels for r in auth)
    rest = [r for r in auth if r[dim]["label"] not in labels]
    hits = [r for r in rest if re.search(pat, corpus(r["repo"])[0], re.I)]
    print(f"  {dim}: labelled {lab_n} ({100*lab_n/len(auth):.1f}%); keyword hit in {len(hits)} of the other {len(rest)}; "
          f"ceiling {lab_n+len(hits)} ({100*(lab_n+len(hits))/len(auth):.1f}%)")
    c = Counter(r[dim]["label"] for r in hits)
    print("      hit rows by label: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))

# Operator-switch share among per-tool narrowing (credential-requiring rows): does the evidence text
# refer to an env var, CLI flag, config setting, read-only mode, allowlist or tool profile?
pt = [r for r in auth if r["scoping_granularity"]["label"] == "per_tool"]
sw = re.compile(r"env|ENV|[A-Z]{3,}_[A-Z_]{3,}|flag|--[a-z]|config|read[- ]?only|allowlist|toolset|disable|enable")
print(f"\nPER-TOOL OPERATOR SWITCH: {sum(bool(sw.search(r['scoping_granularity']['evidence'])) for r in pt)} of {len(pt)} per_tool evidence strings name a switch")
