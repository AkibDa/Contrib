import os
import re

with open("backend/api.py", "r") as f:
    api_code = f.read()

# Replace _do_index with progressive one
api_code = re.sub(r'async def _do_index\(\) -> dict:.*?(?=\n      repo_cache\[cache_key\])', '''
  async def _do_index():
    try:
      import time
      with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = os.path.join(tmp_dir, "cloned_repo")
        yield {"status": "cloning", "repo_url": req.repo_url}
        t_clone_start = time.perf_counter()

        process = await asyncio.to_thread(
          subprocess.run,
          ["git", "clone", "--depth=1", req.repo_url, repo_path],
          capture_output=True,
          text=True,
        )
        t_clone = time.perf_counter() - t_clone_start

        if process.returncode != 0:
          raise RuntimeError(f"Git clone failed: {process.stderr.strip()}")
          
        sha_process = await asyncio.to_thread(
            subprocess.run,
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        commit_sha = sha_process.stdout.strip()

        yield {"status": "ingesting", "clone_time": t_clone}
        t_ingest_start = time.perf_counter()
        summary, tree, content = await ingest_async(repo_path)
        t_ingest = time.perf_counter() - t_ingest_start

      from services import build_query_engine_progressive
      async for event in build_query_engine_progressive(content, repo_name, commit_sha):
          if event["status"] == "bm25_ready":
              engine_bundle = event["bundle"]
              # We can cache the partial bundle
              repo_cache[cache_key] = {
                  "summary": summary,
                  "tree": tree,
                  "engine_bundle": engine_bundle,
              }
              yield {"status": "bm25_ready", "repo_name": repo_name, "summary": summary, "tree": tree}
          elif event["status"] == "ready":
              engine_bundle = event["bundle"]
              repo_cache[cache_key]["engine_bundle"] = engine_bundle
              yield {"status": "ready", "repo_name": repo_name, "summary": summary, "tree": tree}
          else:
              yield event

''', api_code, flags=re.DOTALL)

# Now we need to modify _progressive_load
api_code = re.sub(r'async def _progressive_load.*?async def analyze_issue', '''
async def _progressive_load(
    cache_key: str,
    repo_name: str,
    index_generator_factory,
) -> AsyncGenerator[str, None]:
    """Yield newline-delimited JSON progress events while indexing runs."""
    try:
        async for event in index_generator_factory():
            yield json.dumps(event) + "\\n"
    except Exception as exc:
        yield json.dumps({"status": "error", "detail": repr(exc)}) + "\\n"

@router.post("/analyze-issue")
''', api_code, flags=re.DOTALL)

with open("backend/api.py", "w") as f:
    f.write(api_code)
