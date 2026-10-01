#!/usr/bin/env python3
"""Corpus fetch: README + metadata for each repo in the frame. GitHub API via gh CLI (auth'd, 5k/hr)."""
import json, pathlib, re, subprocess, sys, time

base = pathlib.Path(__file__).parent
frame_md = pathlib.Path("/tmp/awesome-mcp.md").read_text(errors="ignore")
repos = sorted(set(re.findall(r'github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', frame_md)))
repos = [r.rstrip('.') for r in repos if not r.lower().startswith(("punkpeye/", "modelcontextprotocol/"))]
(base / "frame.txt").write_text("\n".join(repos) + "\n")
done_dir = base / "corpus"
log = open(base / "fetch.log", "a")

def gh(args):
    r = subprocess.run(["gh", "api"] + args, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout

fetched = skipped = errors = 0
for i, repo in enumerate(repos):
    out = done_dir / (repo.replace("/", "__") + ".json")
    if out.exists():
        skipped += 1
        continue
    rec = {"repo": repo}
    code, meta = gh([f"repos/{repo}", "--jq", "{stars: .stargazers_count, pushed: .pushed_at, lang: .language, archived: .archived, desc: .description}"])
    if code != 0:
        rec["error"] = "meta_fetch_failed"  # gone/renamed/private
        out.write_text(json.dumps(rec)); errors += 1
        continue
    rec["meta"] = json.loads(meta) if meta.strip() else {}
    code, readme = gh([f"repos/{repo}/readme", "-H", "Accept: application/vnd.github.raw"])
    rec["readme"] = readme[:30000] if code == 0 else None
    # top-level file list (env examples, config names are classification evidence)
    code, tree = gh([f"repos/{repo}/contents", "--jq", "[.[].name]"])
    rec["files"] = json.loads(tree) if code == 0 and tree.strip() else []
    out.write_text(json.dumps(rec))
    fetched += 1
    if (fetched + errors) % 50 == 0:
        print(f"[{i+1}/{len(repos)}] fetched={fetched} skipped={skipped} errors={errors}", file=log, flush=True)
        time.sleep(2)  # gentle pacing
print(f"DONE frame={len(repos)} fetched={fetched} skipped={skipped} errors={errors}", file=log, flush=True)
