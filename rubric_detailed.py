#!/usr/bin/env python3
"""The July 13, 2026 rubric WITH per-label definitions, read verbatim from classify_workflow.js
(the instrument the 1,347 July repos were classified under). Extracted at import time so the
text cannot drift from the committed source. OUTPUT_FORMAT is the JSON-shape block the chunked
CLI drivers need (the July workflow used a tool schema instead); it adds no label guidance.

Sep 30, 2026: classify_full_readme.py's first run imported the CONDENSED rubric from
classify_additions_chunked.py (label names only, no definitions). On identical input that alone
moved the July cohort's revocability labels (shared_key_rotation_only -> insufficient_data, 54 of
179 short-README repos), so that run is kept as a receipt and not used for any published number."""
import os, re
_BASE = os.path.dirname(os.path.abspath(__file__))
_js = open(os.path.join(_BASE, "classify_workflow.js")).read()
_m = re.search(r"const RUBRIC = `(.*?)`\n", _js, re.S)
assert _m, "RUBRIC template literal not found in classify_workflow.js"
RUBRIC_BODY = _m.group(1).replace("\\`", "`")
assert "shared_key_rotation_only: the only way to cut access is rotating a shared key" in RUBRIC_BODY
assert "${" not in RUBRIC_BODY

OUTPUT_FORMAT = """

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

INPUT (JSON array of repos with readme and files):
"""
RUBRIC = RUBRIC_BODY + OUTPUT_FORMAT
if __name__ == "__main__":
    print(RUBRIC)
