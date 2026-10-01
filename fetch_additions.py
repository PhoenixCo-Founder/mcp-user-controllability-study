#!/usr/bin/env python3
"""Sep 10, 2026 refresh: fetch README + metadata for repos ADDED to the frame since Jul 13 (frame-additions-2026-09-10.txt). Same record shape as fetch_corpus.py; skips existing corpus files; never touches frame.txt."""
import json, pathlib, subprocess, time
base = pathlib.Path(__file__).parent
repos = [l.strip() for l in (base / "frame-additions-2026-09-10.txt").read_text().splitlines() if l.strip()]
done_dir = base / "corpus"; done_dir.mkdir(exist_ok=True)
log = open(base / "fetch-additions.log", "a")
def gh(args):
    r = subprocess.run(["gh", "api"] + args, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout
fetched = skipped = errors = 0
for i, repo in enumerate(repos):
    out = done_dir / (repo.replace("/", "__") + ".json")
    if out.exists(): skipped += 1; continue
    rec = {"repo": repo, "frame": "2026-09-10-addition"}
    code, meta = gh([f"repos/{repo}", "--jq", "{stars: .stargazers_count, pushed: .pushed_at, lang: .language, archived: .archived, desc: .description, owner_type: .owner.type, homepage: .homepage}"])
    if code != 0:
        rec["error"] = "meta_fetch_failed"; out.write_text(json.dumps(rec)); errors += 1; continue
    rec["meta"] = json.loads(meta) if meta.strip() else {}
    code, readme = gh([f"repos/{repo}/readme", "-H", "Accept: application/vnd.github.raw"])
    rec["readme"] = readme[:30000] if code == 0 else None
    code, tree = gh([f"repos/{repo}/contents", "--jq", "[.[].name]"])
    rec["files"] = json.loads(tree) if code == 0 and tree.strip() else []
    out.write_text(json.dumps(rec)); fetched += 1
    if (fetched + errors) % 25 == 0:
        print(f"[{i+1}/{len(repos)}] fetched={fetched} skipped={skipped} errors={errors}", file=log, flush=True); time.sleep(2)
print(f"DONE additions={len(repos)} fetched={fetched} skipped={skipped} errors={errors}", file=log, flush=True)
