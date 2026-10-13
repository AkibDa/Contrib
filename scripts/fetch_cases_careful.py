import os
import sys
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from github_client import create_github_client

client = create_github_client()

def get_remaining():
    r = client.get("https://api.github.com/rate_limit")
    if r.status_code == 200:
        return r.json().get("resources", {}).get("core", {}).get("remaining", 0)
    return 0

print(f"Initial remaining rate limit: {get_remaining()}")

CLOSING_PATTERN = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:https?://github\.com/[^/]+/[^/]+/issues/|#)(\d+)",
    re.IGNORECASE,
)

NON_CODE_EXTS = {".md", ".rst", ".txt", ".png", ".jpg", ".svg", ".lock", ".yaml", ".yml", ".json"}

def is_code_file(filename: str) -> bool:
    fn = filename.lower()
    if any(fn.endswith(ext) for ext in NON_CODE_EXTS):
        return False
    if fn.startswith("docs/") or fn.startswith("doc/") or fn.startswith(".github/"):
        return False
    if fn.startswith("tests/") or fn.startswith("test/") or "/tests/" in fn:
        return False
    return True

# Candidate PR lists pre-screened from merged PRs:
# Format: (repo, pr_num, fallback_issue_num)
candidates = [
    # 1. Sherlock
    ("sherlock-project/sherlock", 3038, 3037),
    ("sherlock-project/sherlock", 2929, 2782),
    ("sherlock-project/sherlock", 2921, 2807),
    ("sherlock-project/sherlock", 2919, 2818),
    ("sherlock-project/sherlock", 2853, 2730),
    ("sherlock-project/sherlock", 2267, 2266),
    # 2. pallets/click
    ("pallets/click", 3858, 3822),
    ("pallets/click", 3803, 3802),
    ("pallets/click", 3781, 2869),
    ("pallets/click", 3780, 2582),
    ("pallets/click", 3573, 3571),
    ("pallets/click", 3574, 3572),
    ("pallets/click", 2878, 2877),
    ("pallets/click", 3243, 3242),
    # 3. tqdm/tqdm
    ("tqdm/tqdm", 1829, 1828),
    ("tqdm/tqdm", 1710, 1709),
    ("tqdm/tqdm", 1687, 1686),
    ("tqdm/tqdm", 1582, 1581),
    ("tqdm/tqdm", 1669, 1668),
    ("tqdm/tqdm", 1392, 1391),
    ("tqdm/tqdm", 1287, 1286),
]

cases = []
raw_samples = []

for repo, pr_num, issue_num in candidates:
    rem = get_remaining()
    if rem < 2:
        print(f"Rate limit nearly exhausted ({rem} remaining). Stopping safely.")
        break

    print(f"\nProcessing {repo} PR #{pr_num} -> Issue #{issue_num} (Remaining limit: {rem})")
    
    # 1. Fetch PR details (to get base SHA and body)
    r_pr = client.get(f"https://api.github.com/repos/{repo}/pulls/{pr_num}")
    if r_pr.status_code != 200:
        print(f"LOOKUP FAILED: PR {repo}#{pr_num} returned {r_pr.status_code}: {r_pr.text}")
        sys.exit(1)
    pr_data = r_pr.json()
    base_sha = pr_data.get("base", {}).get("sha", "")
    
    # Check closing reference in PR body if available
    pr_body = pr_data.get("body") or ""
    m = CLOSING_PATTERN.search(pr_body)
    actual_issue_num = int(m.group(1)) if m else issue_num

    # 2. Fetch PR files API
    r_files = client.get(f"https://api.github.com/repos/{repo}/pulls/{pr_num}/files")
    if r_files.status_code != 200:
        print(f"LOOKUP FAILED: PR files {repo}#{pr_num} returned {r_files.status_code}: {r_files.text}")
        sys.exit(1)
    files_data = r_files.json()
    
    if len(files_data) > 5:
        print(f"Skipping {repo}#{pr_num}: touches {len(files_data)} files (> 5)")
        continue
        
    changed_files = [f["filename"] for f in files_data]
    code_files = [f for f in changed_files if is_code_file(f)]
    if not code_files:
        print(f"Skipping {repo}#{pr_num}: tests/docs only ({changed_files})")
        continue

    # 3. Fetch Issue API verbatim
    r_issue = client.get(f"https://api.github.com/repos/{repo}/issues/{actual_issue_num}")
    if r_issue.status_code != 200:
        print(f"LOOKUP FAILED: Issue {repo}#{actual_issue_num} returned {r_issue.status_code}: {r_issue.text}")
        sys.exit(1)
    issue_data = r_issue.json()
    
    case_entry = {
        "id": f"{repo.split('/')[1]}-{actual_issue_num}",
        "repo": repo,
        "issue_url": issue_data["html_url"],
        "pr_url": pr_data["html_url"],
        "base_commit_sha": base_sha,
        "title": issue_data["title"],
        "body": issue_data.get("body") or "",
        "changed_files": changed_files,
        "expected_code_files": code_files,
    }
    cases.append(case_entry)
    print(f"SUCCESS: Added {case_entry['id']}: {case_entry['title'][:50]} (Base: {base_sha[:8]}, files: {changed_files})")

    if len(raw_samples) < 3:
        raw_samples.append({
            "case_id": case_entry["id"],
            "raw_issue_api_response_truncated": {
                "url": issue_data.get("url"),
                "html_url": issue_data.get("html_url"),
                "id": issue_data.get("id"),
                "number": issue_data.get("number"),
                "title": issue_data.get("title"),
                "state": issue_data.get("state"),
                "body": (issue_data.get("body") or "")[:250] + ("..." if len(issue_data.get("body") or "") > 250 else ""),
            },
            "raw_pr_api_response_truncated": {
                "url": pr_data.get("url"),
                "html_url": pr_data.get("html_url"),
                "number": pr_data.get("number"),
                "state": pr_data.get("state"),
                "merged": pr_data.get("merged"),
                "base": {
                    "ref": pr_data.get("base", {}).get("ref"),
                    "sha": pr_data.get("base", {}).get("sha"),
                },
                "head": {
                    "ref": pr_data.get("head", {}).get("ref"),
                    "sha": pr_data.get("head", {}).get("sha"),
                }
            },
            "raw_pr_files_api_response_truncated": [
                {
                    "filename": f.get("filename"),
                    "status": f.get("status"),
                    "additions": f.get("additions"),
                    "deletions": f.get("deletions"),
                }
                for f in files_data[:5]
            ]
        })

print(f"\nTotal valid cases collected: {len(cases)}")
with open(REPO_ROOT / "data" / "eval_cases.json", "w", encoding="utf-8") as f:
    json.dump({"retrieval": cases, "qa": []}, f, indent=2)

with open(REPO_ROOT / "data" / "raw_api_samples.json", "w", encoding="utf-8") as f:
    json.dump(raw_samples, f, indent=2)

print(f"Saved {len(cases)} cases to data/eval_cases.json")
print("Saved 3 raw API samples to data/raw_api_samples.json")
