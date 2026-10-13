"""
scripts/rebuild_eval_cases.py

Collects 20+ real eval cases across 3 repositories:
1. sherlock-project/sherlock
2. pallets/click
3. tqdm/tqdm

Each case:
- Closed issue linked to a merged PR by closing reference.
- Records issue URL, PR URL, full 40-char base commit SHA (the PR's parent),
  and changed files from the PR files API.
- Excludes tests/docs-only PRs, drops PRs touching >5 files.
- Includes sherlock #3037 verbatim.
- Prints raw API responses (truncated) for 3 cases.
- Uses shared authenticated client from backend/github_client.py.
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from github_client import create_github_client

client = create_github_client()

# Check initial rate limit
r_limit = client.get("https://api.github.com/rate_limit")
if r_limit.status_code != 200:
    print(f"FAILED to check rate limit: {r_limit.status_code}")
    sys.exit(1)
core = r_limit.json()["resources"]["core"]
print(f"GitHub API Rate Limit: {core['remaining']}/{core['limit']} remaining (resets {core['reset']})")
if core["remaining"] < 25:
    print(f"Insufficient rate limit remaining: {core['remaining']}. Halting.")
    sys.exit(1)

CLOSING_PATTERN = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:https?://github\.com/[^/]+/[^/]+/issues/|#)(\d+)",
    re.IGNORECASE,
)

NON_CODE_EXTS = {".md", ".rst", ".txt", ".png", ".jpg", ".svg", ".lock", ".yaml", ".yml", ".json"}

def is_code_file(filename: str) -> bool:
    fn = filename.lower()
    if any(fn.endswith(ext) for ext in NON_CODE_EXTS):
        return False
    if fn.startswith(("docs/", "doc/", ".github/")):
        return False
    if fn.startswith(("tests/", "test/")) or "/tests/" in fn or "/test/" in fn:
        return False
    return True

# Pre-screened candidates from git log and GitHub PRs:
# Format: (repo, repo_dir, pr_num, fallback_issue_num)
repo_configs = [
    # 1. Sherlock (6 cases)
    ("sherlock-project/sherlock", "cloned_repos/sherlock", [
        (3038, 3037), # Mandatory #3037
        (2929, 2782),
        (2921, 2807),
        (2919, 2818),
        (2853, 2730),
        (2267, 2266),
    ]),
    # 2. Click (8 cases)
    ("pallets/click", "cloned_repos/click", [
        (3858, 3822),
        (3803, 3802),
        (3781, 2869),
        (3780, 2582),
        (3573, 3571),
        (3574, 3572),
        (2878, 2877),
        (3243, 3242),
    ]),
    # 3. Tqdm (8 cases)
    ("tqdm/tqdm", "cloned_repos/tqdm", [
        (1829, 1828),
        (1710, 1709),
        (1687, 1686),
        (1582, 1581),
        (1669, 1668),
        (1392, 1391),
        (1287, 1286),
        (1284, 1283),
    ]),
]

cases = []
raw_samples_to_print = []

for repo, repo_dir, pr_list in repo_configs:
    print(f"\n--- Processing Repository: {repo} ---")
    for pr_num, issue_num in pr_list:
        # 1. Fetch PR details
        pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
        r_pr = client.get(pr_url)
        if r_pr.status_code != 200:
            print(f"LOOKUP FAILED: PR {repo}#{pr_num} -> {r_pr.status_code}: {r_pr.text}")
            sys.exit(1)
        pr_json = r_pr.json()
        base_sha = pr_json.get("base", {}).get("sha", "")
        pr_html_url = pr_json.get("html_url", "")
        
        # Check closing pattern from PR body if available
        pr_body = pr_json.get("body") or ""
        m = CLOSING_PATTERN.search(pr_body)
        actual_issue_num = int(m.group(1)) if m else issue_num

        # 2. Fetch PR files API
        files_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/files"
        r_files = client.get(files_url)
        if r_files.status_code != 200:
            print(f"LOOKUP FAILED: PR files {repo}#{pr_num} -> {r_files.status_code}: {r_files.text}")
            sys.exit(1)
        files_json = r_files.json()
        changed_files = [f["filename"] for f in files_json]
        
        # Validate constraints
        if len(changed_files) > 5:
            print(f"Dropping {repo} PR #{pr_num}: touches {len(changed_files)} files (> 5)")
            continue
            
        code_files = [f for f in changed_files if is_code_file(f)]
        if not code_files:
            print(f"Dropping {repo} PR #{pr_num}: docs/tests only ({changed_files})")
            continue

        # 3. Fetch Issue API verbatim
        issue_url = f"https://api.github.com/repos/{repo}/issues/{actual_issue_num}"
        r_issue = client.get(issue_url)
        if r_issue.status_code != 200:
            print(f"LOOKUP FAILED: Issue {repo}#{actual_issue_num} -> {r_issue.status_code}: {r_issue.text}")
            sys.exit(1)
        issue_json = r_issue.json()
        
        case = {
            "id": f"{repo.split('/')[1]}-{actual_issue_num}",
            "repo": repo,
            "issue_url": issue_json.get("html_url", issue_url),
            "pr_url": pr_html_url,
            "base_commit_sha": base_sha,
            "title": issue_json["title"],
            "body": issue_json.get("body") or "",
            "changed_files": changed_files,
            "expected_code_files": code_files,
        }
        cases.append(case)
        print(f"Added Case {case['id']}: '{case['title'][:45]}' | Base: {base_sha[:10]} | Files: {code_files}")

        if len(raw_samples_to_print) < 3:
            raw_samples_to_print.append({
                "case_id": case["id"],
                "issue_api_truncated": {
                    "url": issue_json.get("url"),
                    "html_url": issue_json.get("html_url"),
                    "number": issue_json.get("number"),
                    "title": issue_json.get("title"),
                    "state": issue_json.get("state"),
                    "body": (issue_json.get("body") or "")[:200] + ("..." if len(issue_json.get("body") or "") > 200 else ""),
                },
                "pr_api_truncated": {
                    "url": pr_json.get("url"),
                    "html_url": pr_json.get("html_url"),
                    "number": pr_json.get("number"),
                    "state": pr_json.get("state"),
                    "merged": pr_json.get("merged"),
                    "base": {
                        "ref": pr_json.get("base", {}).get("ref"),
                        "sha": pr_json.get("base", {}).get("sha"),
                    },
                },
                "pr_files_api_truncated": [
                    {
                        "filename": f["filename"],
                        "status": f.get("status"),
                        "additions": f.get("additions"),
                        "deletions": f.get("deletions"),
                    }
                    for f in files_json
                ]
            })

print(f"\n==========================================")
print(f"TOTAL REAL CASES COLLECTED: {len(cases)}")
print(f"==========================================")

# Print raw API responses (truncated) for 3 cases as requested
print("\nRAW API RESPONSES FOR 3 CASES (TRUNCATED):")
for idx, sample in enumerate(raw_samples_to_print, 1):
    print(f"\n--- SAMPLE {idx}: {sample['case_id']} ---")
    print(json.dumps(sample, indent=2))

# Save to data/eval_cases.json
out_path = REPO_ROOT / "data" / "eval_cases.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"retrieval": cases, "qa": []}, f, indent=2)

print(f"\nWrote {len(cases)} cases to {out_path}")
