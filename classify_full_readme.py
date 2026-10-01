#!/usr/bin/env python3
"""Re-classify the whole study frame on FULL READMEs (Sep 30, 2026).

Why: the committed labels (classifications-2026-09-15.jsonl) were produced from README
slices (3,500 chars for the July cohort, 4,000 for the Sep 15 additions). 82% of corpus
READMEs are longer. On a 20-repo sample, giving the same classifier the full README
changed 38/120 cells and raised agreement with an independent reviewer from 70.8% to
85.0% (truncation_effect-2026-09-30.md). This run classifies every frame repo once, with
one pinned model, on the full stored README (fetch cap 30,000 chars, disclosed).

Prompt = a committed rubric + the JSON records, same record shape as the committed compact
batches (repo, stars, lang, readme, files).

RUBRIC CHOICE (corrected Sep 30 16:50 PT): run 1 (tag 2026-09-30) imported the CONDENSED rubric
from classify_additions_chunked.py (label names, no definitions). The 1,347 July repos were
originally classified under the DETAILED rubric in classify_workflow.js (per-label definitions).
On identical input that rubric swap alone moved labels (July short-README revocability 55%
unchanged vs 92% for the additions cohort), so run 1 is a receipt, not a dataset. Default is now
--rubric detailed (rubric_detailed.py, verbatim from classify_workflow.js) with its own --tag.

Usage:
  python3 classify_full_readme.py                 # full run (resumable; re-run to continue)
  python3 classify_full_readme.py --limit 1       # smoke: first chunk only
  python3 classify_full_readme.py --merge-only    # merge finished chunks into the jsonl
  python3 classify_full_readme.py --tag NAME --rubric detailed|condensed --repos-file FILE
      --tag         output namespace (default 2026-09-30-v2; run 1 lives under 2026-09-30)
      --repos-file  classify only these repos (one owner/name per line), e.g. a repeat-run sample

Output dir: full-readme-<tag>/
  chunks/NNNN.jsonl   one file per finished chunk (checkpoint)
  failures.jsonl      chunks that failed after retries (repo list + reason)
  progress.json       live counters (read by the completion cron)
  meta.json           model, chunking, caps, start/end
  ../classifications-full-readme-<tag>.jsonl   merged rows, same shape as committed
"""
import ast, json, os, subprocess, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify_additions_chunked as cac  # RUBRIC, VALID_LABELS, DIMS, extract_classifications_json (module has a __main__ guard)

BASE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(BASE, "corpus")
FRAME_FILE = os.path.join(BASE, "classifications-2026-09-15.jsonl")   # the 1,634 classified repos = the frame
def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
TAG = _arg("--tag", "2026-09-30-v2")
RUBRIC_NAME = _arg("--rubric", "detailed")
REPOS_FILE = _arg("--repos-file")
assert RUBRIC_NAME in ("detailed", "condensed")
if RUBRIC_NAME == "detailed":
    import rubric_detailed
    RUBRIC = rubric_detailed.RUBRIC
    RUBRIC_SOURCE = "rubric_detailed.RUBRIC (classify_workflow.js July rubric, verbatim, + JSON output-format block)"
else:
    RUBRIC = cac.RUBRIC
    RUBRIC_SOURCE = "classify_additions_chunked.RUBRIC (condensed, unchanged)"
OUT_DIR = os.path.join(BASE, f"full-readme-{TAG}")
CHUNK_DIR = os.path.join(OUT_DIR, "chunks")
MERGED = os.path.join(BASE, f"classifications-full-readme-{TAG}.jsonl")
MODEL = "claude-sonnet-5-5"          # pinned + recorded (July cohort ran on Sonnet; Sep 15 additions ran on the CLI default)
MAX_REPOS = 5                        # same chunk ceiling as classify_additions_chunked.py
MAX_CHARS = 90_000                   # readme chars per chunk (~25K tokens) so one call never balloons
README_CAP = 30_000                  # the fetch scripts stored at most 30,000 chars; nothing is sliced below that here
WORKERS = 4
TIMEOUT = 900
RETRIES = 2

def load_records():
    if os.path.exists(FRAME_FILE):
        repos = [json.loads(l)["repo"] for l in open(FRAME_FILE) if l.strip()]
    else:  # public package: the label file is not shipped, the repo list is
        repos = [l.strip() for l in open(os.path.join(BASE, "frame-classified-1634.txt")) if l.strip()]
    if REPOS_FILE:
        keep = {l.strip() for l in open(REPOS_FILE) if l.strip()}
        missing = keep - set(repos)
        assert not missing, f"repos-file entries not in frame: {sorted(missing)[:5]}"
        repos = [r for r in repos if r in keep]
    recs = []
    for repo in repos:
        d = json.load(open(os.path.join(CORPUS, repo.replace("/", "__") + ".json")))
        meta = d.get("meta", {})
        if isinstance(meta, str):
            try: meta = ast.literal_eval(meta)
            except Exception: meta = {}
        files = d.get("files", [])
        if isinstance(files, str):
            try: files = ast.literal_eval(files)
            except Exception: files = []
        readme = (d.get("readme", "") or "")[:README_CAP]
        recs.append({"repo": repo, "stars": meta.get("stargazers_count", meta.get("stars", 0)) or 0,
                     "lang": meta.get("language", meta.get("lang", "")) or "", "readme": readme, "files": files})
    return recs

def make_chunks(recs):
    chunks, cur, cur_chars = [], [], 0
    for r in recs:
        n = len(r["readme"])
        if cur and (len(cur) >= MAX_REPOS or cur_chars + n > MAX_CHARS):
            chunks.append(cur); cur, cur_chars = [], 0
        cur.append(r); cur_chars += n
    if cur: chunks.append(cur)
    return chunks

def classify(chunk):
    prompt = RUBRIC + json.dumps(chunk, indent=2)
    want = {r["repo"] for r in chunk}
    last = ""
    for attempt in range(RETRIES + 1):
        try:
            res = subprocess.run(["claude", "-p", "--model", MODEL, "--output-format", "json"],
                                 input=prompt, capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            last = "timeout"; time.sleep(10); continue
        if res.returncode != 0:
            last = f"rc={res.returncode} {res.stderr[:200]}"; time.sleep(15 * (attempt + 1)); continue
        inner = cac.extract_classifications_json(res.stdout.strip())
        if inner is None:
            last = "no classifications JSON"; time.sleep(5); continue
        rows = []
        for c in inner.get("classifications", []):
            row = {"repo": c.get("repo", "")}
            for dim in cac.DIMS:
                d = c.get(dim, {}) if isinstance(c.get(dim), dict) else {}
                label = d.get("label", "insufficient_data")
                if label not in cac.VALID_LABELS[dim]:
                    label = "insufficient_data"
                row[dim] = {"label": label, "evidence": d.get("evidence", "no evidence provided")}
            rows.append(row)
        got = {r["repo"] for r in rows}
        if got != want:   # Sep 15 lesson: a chunk once came back 19/20 and silently dropped a repo
            last = f"row mismatch missing={sorted(want - got)} extra={sorted(got - want)}"; continue
        try:
            env = json.loads(res.stdout)
            used = env.get("modelUsage") or {}
        except Exception:
            used = {}
        return rows, {"model_usage_keys": list(used.keys()), "attempt": attempt}, None
    return None, None, last

_lock = threading.Lock()
def write_progress(done, failed, total, started):
    with _lock:
        json.dump({"done_chunks": done, "failed_chunks": failed, "total_chunks": total,
                   "started": started, "updated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   "finished": done + failed >= total}, open(os.path.join(OUT_DIR, "progress.json"), "w"), indent=1)

def merge(chunks):
    rows = []
    for i in range(len(chunks)):
        p = os.path.join(CHUNK_DIR, f"{i:04d}.jsonl")
        if os.path.exists(p):
            rows += [json.loads(l) for l in open(p) if l.strip()]
    with open(MERGED, "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    return len(rows)

def main():
    limit = None
    if "--limit" in sys.argv: limit = int(sys.argv[sys.argv.index("--limit") + 1])
    os.makedirs(CHUNK_DIR, exist_ok=True)
    recs = load_records(); chunks = make_chunks(recs)
    if "--merge-only" in sys.argv:
        print("merged rows:", merge(chunks)); return
    if limit: chunks_to_run = list(range(limit))
    else: chunks_to_run = list(range(len(chunks)))
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    meta = {"model": MODEL, "readme_cap_chars": README_CAP, "max_repos_per_chunk": MAX_REPOS, "max_chars_per_chunk": MAX_CHARS,
            "workers": WORKERS, "frame_file": os.path.basename(FRAME_FILE), "repos": len(recs), "chunks": len(chunks),
            "total_readme_chars": sum(len(r["readme"]) for r in recs), "rubric_source": RUBRIC_SOURCE, "rubric": RUBRIC_NAME, "tag": TAG, "repos_file": REPOS_FILE,
            "started": started, "limit": limit}
    json.dump(meta, open(os.path.join(OUT_DIR, "meta.json"), "w"), indent=1)
    pending = [i for i in chunks_to_run if not os.path.exists(os.path.join(CHUNK_DIR, f"{i:04d}.jsonl"))]
    done = len(chunks_to_run) - len(pending); failed = 0
    print(f"repos={len(recs)} chunks={len(chunks)} run={len(chunks_to_run)} already_done={done} pending={len(pending)} model={MODEL}", flush=True)
    write_progress(done, failed, len(chunks_to_run), started)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(classify, chunks[i]): i for i in pending}
        for fut in as_completed(futs):
            i = futs[fut]; rows, info, err = fut.result()
            if rows is None:
                failed += 1
                with _lock, open(os.path.join(OUT_DIR, "failures.jsonl"), "a") as f:
                    f.write(json.dumps({"chunk": i, "repos": [r["repo"] for r in chunks[i]], "error": err, "at": time.strftime("%H:%M:%S")}) + "\n")
                print(f"chunk {i:04d} FAILED: {err}", flush=True)
            else:
                with open(os.path.join(CHUNK_DIR, f"{i:04d}.jsonl"), "w") as f:
                    for r in rows: f.write(json.dumps(r) + "\n")
                done += 1
                el = time.time() - t0; rate = (done + failed - (len(chunks_to_run) - len(pending))) / max(el, 1)
                left = (len(pending) - (done + failed - (len(chunks_to_run) - len(pending)))) / max(rate, 1e-9)
                print(f"chunk {i:04d} ok ({len(rows)} rows, attempt {info['attempt']}) done={done}/{len(chunks_to_run)} failed={failed} eta={left/60:.0f}m", flush=True)
            write_progress(done, failed, len(chunks_to_run), started)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z"); meta["done_chunks"] = done; meta["failed_chunks"] = failed
    meta["merged_rows"] = merge(chunks) if not limit else None
    json.dump(meta, open(os.path.join(OUT_DIR, "meta.json"), "w"), indent=1)
    print("FINISHED", json.dumps({k: meta[k] for k in ("done_chunks", "failed_chunks", "merged_rows", "finished")}), flush=True)

if __name__ == "__main__":
    main()
