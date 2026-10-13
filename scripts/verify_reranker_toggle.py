"""
scripts/verify_reranker_toggle.py

Demonstrates:
1. How backend/services.py imports rerank:
   `from reranker import rerank` (line 47 of backend/services.py).
2. Verifies that the toggle takes effect through the configuration flag
   `RERANKER_ENABLED` environment variable and `Settings.reranker_enabled`
   (config flag, not monkeypatching).
3. Proves that retrieval outputs (scores and file ranks) differ between
   reranker ON and reranker OFF.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import config
import services
from eval_retrieval import load_cached_repo_bundle

print("=" * 70)
print("VERIFY RERANKER TOGGLE IN Contrib")
print("=" * 70)

# 1. Show import in services.py
print("\n[Step 1: Check Import in backend/services.py]")
with open(REPO_ROOT / "backend" / "services.py", "r", encoding="utf-8") as f:
    services_lines = f.readlines()

import_lines = [(i + 1, line.strip()) for i, line in enumerate(services_lines) if "from reranker import rerank" in line]
for line_no, line_text in import_lines:
    print(f"  Line {line_no}: {line_text}")

print(f"  Imported symbol in services: {services.rerank}")

# 2. Load bundle
print("\n[Step 2: Load Indexed Bundle]")
bundle = load_cached_repo_bundle("idx_4686cca7a29cf9ca", "idx_4686cca7a29cf9ca")
print(f"  Loaded bundle with {len(bundle['sources'])} sources.")

# 3. Run with Reranker ON via Config Flag
print("\n[Step 3: Run Retrieval with Reranker ON (RERANKER_ENABLED=true)]")
os.environ["RERANKER_ENABLED"] = "true"
config.settings = config.Settings()
services.settings = config.settings
print(f"  config.settings.reranker_enabled: {config.settings.reranker_enabled}")

query = "Break down sherlock() function into helper functions"
res_on = services.run_retrieval_agent(bundle, query, top_k=10)
files_on = [f["path"] for f in res_on["relevant_files"]]
scores_on = [round(f["score"], 4) for f in res_on["relevant_files"]]

for rank, (fp, score) in enumerate(zip(files_on, scores_on), 1):
    print(f"  Rank {rank:2d}: {fp:<35} score={score}")

# 4. Run with Reranker OFF via Config Flag
print("\n[Step 4: Run Retrieval with Reranker OFF (RERANKER_ENABLED=false)]")
os.environ["RERANKER_ENABLED"] = "false"
config.settings = config.Settings()
services.settings = config.settings
print(f"  config.settings.reranker_enabled: {config.settings.reranker_enabled}")

res_off = services.run_retrieval_agent(bundle, query, top_k=10)
files_off = [f["path"] for f in res_off["relevant_files"]]
scores_off = [round(f["score"], 4) for f in res_off["relevant_files"]]

for rank, (fp, score) in enumerate(zip(files_off, scores_off), 1):
    print(f"  Rank {rank:2d}: {fp:<35} score={score}")


# 5. Difference Check
print("\n[Step 5: Output Comparison]")
print(f"  File ordering identical: {files_on == files_off}")
print(f"  Scores identical:        {scores_on == scores_off}")
print(f"  Reranker metadata ON:    confidence_score={res_on.get('reranker', {}).get('confidence_score')}, tier={res_on.get('reranker', {}).get('confidence_tier')}")
print(f"  Reranker metadata OFF:   explanation='{res_off.get('reranker', {}).get('explanation')}'")

assert scores_on != scores_off, "Scores must differ between reranker ON and OFF!"
assert res_on.get("reranker", {}).get("confidence_tier") is not None, "ON run must have confidence_tier!"
assert res_off.get("reranker", {}).get("explanation") == "Reranker disabled via configuration", "OFF run must state reranker disabled!"

print("\nSUCCESS: Reranker toggle verified via config flag without monkeypatching!")
