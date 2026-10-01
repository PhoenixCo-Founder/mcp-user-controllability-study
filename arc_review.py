#!/usr/bin/env python3
"""Tally the hand review of the rows the classifier labelled `agent_reachable_consent`.

The review file is one JSON object per flagged repository (category + the README
passage the category rests on). This script checks that the review covers exactly
the flagged rows of the classification file, then prints the tallies quoted in the
post. The labels in the classification file are NOT overridden by the review.

Usage: python3 arc_review.py [classifications.jsonl] [review.jsonl]
"""
import collections
import json
import sys

CLS = sys.argv[1] if len(sys.argv) > 1 else "classifications-full-readme-2026-09-30-v2.jsonl"
REV = sys.argv[2] if len(sys.argv) > 2 else "review-agent-reachable-2026-09-30.jsonl"


def main():
    flagged = set()
    with open(CLS) as f:
        for line in f:
            r = json.loads(line)
            if r["consent_surface"]["label"] == "agent_reachable_consent":
                flagged.add(r["repo"])
    review = [json.loads(line) for line in open(REV) if line.strip()]
    reviewed = [r["repo"] for r in review]
    assert len(reviewed) == len(set(reviewed)), "duplicate repo in review file"
    assert set(reviewed) == flagged, (sorted(flagged - set(reviewed)), sorted(set(reviewed) - flagged))

    cats = collections.Counter(r["category"] for r in review)
    top = collections.Counter(r["category"].split(":")[0] for r in review)
    print(f"flagged agent_reachable_consent rows: {len(flagged)}; hand-reviewed: {len(review)}")
    print("\nBY CATEGORY")
    for k, v in sorted(top.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
        for k2, v2 in sorted(cats.items(), key=lambda kv: -kv[1]):
            if ":" in k2 and k2.split(":")[0] == k:
                print(f"      {k2.split(':')[1]}: {v2}")
    done = [r for r in review if r["category"].startswith("agent_completes")]
    print(f"\nconfirmation completed in the agent's own tool call: {len(done)} of {len(review)}")
    print(f"  of those, README says the agent cannot bypass/skip the step: "
          f"{sum(1 for r in done if r.get('claims_agent_cannot_bypass'))}")
    print(f"READMEs (all {len(review)}) that state the limit of their own confirmation step: "
          f"{sum(1 for r in review if r.get('self_discloses_limit'))}")


if __name__ == "__main__":
    main()
