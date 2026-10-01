#!/usr/bin/env python3
"""Classify addition batches in chunks of 5 repos to avoid CLI timeouts."""

import json
import os
import re
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
BATCHES_DIR = os.path.join(BASE, "batches", "compact-additions")
NUM_BATCHES = 15
CHUNK_SIZE = 5

RUBRIC = """You are classifying Model Context Protocol (MCP) server repositories on 6 USER-CONTROLLABILITY dimensions. This is STATIC ANALYSIS of DOCUMENTED capability only (README + top-level file names).

CRITICAL RULES:
- Every label MUST be justified by a DIRECT QUOTE from the README, or by a specific filename. Put that in the "evidence" field.
- If docs don't contain enough info, use "insufficient_data" and explain what was missing. NEVER guess.
- Keyword matching is NOT sufficient. Filesystem "scope" != auth scoping. "PRIVATE_KEY" for crypto = static key. Read for MEANING.
- Judge the AUTH/CREDENTIAL path a human uses to connect an agent to this server.

THE 6 DIMENSIONS AND ALLOWED LABELS:

1. credential_delivery: env_var_static_key | config_file | oauth_redirect | user_mediated | none_needed | insufficient_data
2. scoping_granularity: all_or_nothing | per_user | per_tool | per_action | user_selected_scope | none | insufficient_data
3. revocability: documented_revocation | shared_key_rotation_only | redeploy_only | none | insufficient_data
4. credential_lifetime: long_lived_static | expiring | user_chosen_duration | none | insufficient_data
5. consent_surface: connection_time_approval | agent_reachable_consent | none | insufficient_data
6. attribution: per_user_agent_attribution | shared_identity | insufficient_data

OUTPUT FORMAT: Return a JSON object with a "classifications" array. Each element has:
{
  "repo": "owner/name",
  "credential_delivery": {"label": "...", "evidence": "..."},
  "scoping_granularity": {"label": "...", "evidence": "..."},
  "revocability": {"label": "...", "evidence": "..."},
  "credential_lifetime": {"label": "...", "evidence": "..."},
  "consent_surface": {"label": "...", "evidence": "..."},
  "attribution": {"label": "...", "evidence": "..."}
}

Classify EVERY repo in the input array. Evidence is MANDATORY.

INPUT (JSON array of repos with readme and files):\n"""

VALID_LABELS = {
    "credential_delivery": {"env_var_static_key","config_file","oauth_redirect","user_mediated","none_needed","insufficient_data"},
    "scoping_granularity": {"all_or_nothing","per_user","per_tool","per_action","user_selected_scope","none","insufficient_data"},
    "revocability": {"documented_revocation","shared_key_rotation_only","redeploy_only","none","insufficient_data"},
    "credential_lifetime": {"long_lived_static","expiring","user_chosen_duration","none","insufficient_data"},
    "consent_surface": {"connection_time_approval","agent_reachable_consent","none","insufficient_data"},
    "attribution": {"per_user_agent_attribution","shared_identity","insufficient_data"},
}
DIMS = list(VALID_LABELS.keys())

def extract_classifications_json(raw):
    """claude --output-format json wraps the answer in an envelope whose "result" is a STRING.
    The model often returns prose + a ```json fenced block, so: unwrap the envelope first, then
    search the unescaped result text (never the raw envelope, where quotes are backslash-escaped)."""
    text = raw
    try:
        outer = json.loads(raw)
        if isinstance(outer, dict) and "result" in outer:
            text = outer["result"] if isinstance(outer["result"], str) else json.dumps(outer["result"])
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [m.group(1)] if m else []
    if '"classifications"' in text:
        start = text.find("{"); end = text.rfind("}")
        if start != -1 and end > start:
            candidates.append(text[start:end + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict) and "classifications" in obj:
                return obj
            # chunk-of-1 calls come back as a bare row object (seen Sep 15 2026); wrap it
            if isinstance(obj, dict) and "repo" in obj and "consent_surface" in obj:
                return {"classifications": [obj]}
        except Exception:
            continue
    return None

def classify_chunk(repos, batch_idx, chunk_idx):
    """Classify a small chunk of repos. Returns list of row dicts or None on failure."""
    prompt = RUBRIC + json.dumps(repos, indent=2)
    print(f"    chunk {batch_idx:03d}/{chunk_idx}: classifying {len(repos)} repos...", flush=True)

    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        capture_output=True, text=True, timeout=600
    )

    if result.returncode != 0:
        print(f"    chunk {batch_idx:03d}/{chunk_idx} ERROR rc={result.returncode}: {result.stderr[:200]}")
        return None

    raw = result.stdout.strip()
    inner = extract_classifications_json(raw)
    if inner is None:
        print(f"    chunk {batch_idx:03d}/{chunk_idx}: no classifications JSON in output. raw[:200]: {raw[:200]}")
        return None

    classifications = inner.get("classifications", [])
    rows = []
    for c in classifications:
        row = {"repo": c.get("repo", "")}
        for dim in DIMS:
            d = c.get(dim, {})
            label = d.get("label", "insufficient_data")
            if label not in VALID_LABELS[dim]:
                label = "insufficient_data"
            row[dim] = {"label": label, "evidence": d.get("evidence", "no evidence provided")}
        rows.append(row)
    return rows

def classify_batch(batch_idx):
    out_path = os.path.join(BASE, f"temp_add_{batch_idx:03d}.jsonl")
    if os.path.exists(out_path):
        lines = [l for l in open(out_path) if l.strip()]
        if lines:
            print(f"  batch {batch_idx:03d}: already has {len(lines)} lines, skipping")
            return True

    batch_path = os.path.join(BATCHES_DIR, f"{batch_idx:03d}.json")
    repos = json.load(open(batch_path))
    print(f"  batch {batch_idx:03d}: {len(repos)} repos, chunking into {CHUNK_SIZE}s...", flush=True)

    all_rows = []
    for chunk_idx, start in enumerate(range(0, len(repos), CHUNK_SIZE)):
        chunk = repos[start:start + CHUNK_SIZE]
        rows = classify_chunk(chunk, batch_idx, chunk_idx)
        if rows is None:
            print(f"  batch {batch_idx:03d}: chunk {chunk_idx} failed")
            return False
        got = {r["repo"] for r in rows}
        want = {r["repo"] for r in chunk}
        if got != want:
            # Sep 15 2026: batch 010 silently came back 19/20 and dropped a repo. Never again.
            print(f"  batch {batch_idx:03d}: chunk {chunk_idx} ROW MISMATCH missing={sorted(want - got)} extra={sorted(got - want)}")
            return False
        all_rows.extend(rows)
        print(f"    chunk {batch_idx:03d}/{chunk_idx}: got {len(rows)} rows", flush=True)

    with open(out_path, "w") as f:
        f.write("\n".join(json.dumps(r) for r in all_rows) + "\n")

    print(f"  batch {batch_idx:03d}: wrote {len(all_rows)} rows to {os.path.basename(out_path)}")
    return True

if __name__ == "__main__":
    start_batch = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end_batch = int(sys.argv[2]) if len(sys.argv) > 2 else NUM_BATCHES

    print(f"Classifying batches {start_batch}-{end_batch-1} in chunks of {CHUNK_SIZE}...")
    failed = []
    for i in range(start_batch, end_batch):
        t = time.time()
        ok = classify_batch(i)
        if not ok:
            failed.append(i)
        print(f"    done in {time.time()-t:.1f}s", flush=True)

    if failed:
        print(f"\nFailed batches: {failed}")
        sys.exit(1)
    else:
        print(f"\nAll batches {start_batch}-{end_batch-1} complete.")
