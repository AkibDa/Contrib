"""
scripts/fetch_eval_cases.py

Fetches closed issues linked to merged PRs by closing references across 3 repos:
1. sherlock-project/sherlock
2. pallets/click
3. encode/httpx

Filters:
- Excludes tests/docs-only PRs
- Drops PRs touching > 5 files
- Captures issue URL, PR URL, 40-char base commit SHA, changed files, verbatim issue title and body.
Uses shared authenticated client with GITHUB_TOKEN from environment.
If a lookup fails (e.g. rate limit), stops and reports failure.
"""

import os
import sys
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from github_client import create_github_client

client = create_github_client()

# Check rate limit first
r_rate = client.get("https://api.github.com/rate_limit")
if r_rate.status_code == 200:
    core = r_rate.json().get("resources", {}).get("core", {})
    remaining = core.get("remaining", 0)
    limit = core.get("limit", 60)
    print(f"GitHub API Rate Limit: {remaining}/{limit} remaining (reset: {core.get('reset')})")
else:
    print(f"Failed to check rate limit: HTTP {r_rate.status_code}")
    sys.exit(1)

repos = ["sherlock-project/sherlock", "pallets/click", "encode/httpx"]
cases = []
raw_samples = []

CLOSING_PATTERN = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:https?://github\.com/[^/]+/[^/]+/issues/|#)(\d+)",
    re.IGNORECASE,
)

NON_CODE_EXTS = {".md", ".rst", ".txt", ".png", ".jpg", ".svg", ".lock"}

def is_code_file(filename: str) -> bool:
    fn = filename.lower()
    if any(fn.endswith(ext) for ext in NON_CODE_EXTS):
        return False
    if fn.startswith("docs/") or fn.startswith("doc/") or fn.startswith(".github/"):
        return False
    if fn.startswith("tests/") or fn.startswith("test/") or "/tests/" in fn:
        return False
    return True

print("\nStarting lookup across repositories...")

# Always include sherlock #3037 as explicitly requested
print("\n[Case 1: Mandatory Sherlock #3037]")
r_3037 = client.get("https://api.github.com/repos/sherlock-project/sherlock/issues/3037")
if r_3037.status_code != 200:
    print(f"FAILED to fetch Sherlock #3037: HTTP {r_3037.status_code} - {r_3037.text}")
    sys.exit(1)

data_3037 = r_3037.json()
r_3038 = client.get("https://api.github.com/repos/sherlock-project/sherlock/pulls/3038")
if r_3038.status_code != 200:
    print(f"FAILED to fetch Sherlock PR #3038: HTTP {r_3038.status_code} - {r_3038.text}")
    sys.exit(1)

pr_3038_data = r_3038.json()
r_3038_files = client.get("https://api.github.com/repos/sherlock-project/sherlock/pulls/3038/files")
if r_3038_files.status_code != 200:
    print(f"FAILED to fetch PR #3038 files: HTTP {r_3038_files.status_code} - {r_3038_files.text}")
    sys.exit(1)

files_3038 = [f["filename"] for f in r_3038_files.json()]
case_3037 = {
    "id": "sherlock-3037",
    "repo": "sherlock-project/sherlock",
    "issue_url": "https://github.com/sherlock-project/sherlock/issues/3037",
    "pr_url": "https://github.com/sherlock-project/sherlock/pull/3038",
    "base_commit_sha": pr_3038_data["base"]["sha"],
    "title": data_3037["title"],
    "body": data_3037["body"] or "",
    "changed_files": files_3038,
}
cases.append(case_3037)
raw_samples.append({
    "case_id": "sherlock-3037",
    "issue_api_sample": {
        "url": data_3037["url"],
        "title": data_3037["title"],
        "state": data_3037["state"],
        "body_preview": (data_3037["body"] or "")[:150],
    },
    "pr_api_sample": {
        "url": pr_3038_data["url"],
        "base_sha": pr_3038_data["base"]["sha"],
        "files": files_3038,
    }
})
print("Sherlock #3037 collected successfully.")

for repo in repos:
    print(f"\nScanning repo: {repo}...")
    page = 1
    while len([c for c in cases if c["repo"] == repo]) < 8:
        url = f"https://api.github.com/repos/{repo}/pulls?state=closed&per_page=30&page={page}"
        r = client.get(url)
        if r.status_code == 403 or r.status_code == 429:
            print(f"LOOKUP FAILED: Rate limit exceeded on {url}. Status {r.status_code}: {r.text}")
            print("Stopping per instructions: 'If a lookup fails, say so and stop instead of filling in data.'")
            sys.exit(1)
        if r.status_code != 200:
            print(f"LOOKUP FAILED: HTTP {r.status_code} on {url}: {r.text}")
            sys.exit(1)

        prs = r.json()
        if not prs:
            break

        for pr in prs:
            if not pr.get("merged_at"):
                continue

            pr_body = pr.get("body") or ""
            match = CLOSING_PATTERN.search(pr_body)
            if not match:
                continue

            issue_num = int(match.group(1))
            pr_num = pr["number"]
            base_sha = pr.get("base", {}).get("sha", "")

            # Check files
            f_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/files"
            r_files = client.get(f_url)
            if r_files.status_code == 403 or r_files.status_code == 429:
                print(f"LOOKUP FAILED: Rate limit exceeded on {f_url}. Status {r_files.status_code}")
                sys.exit(1)
            if r_files.status_code != 200:
                continue

            files_data = r_files.json()
            if not files_data or len(files_data) > 5:
                continue

            changed_files = [f["filename"] for f in files_data]
            code_files = [f for f in changed_files if is_code_file(f)]
            if not code_files:
                # Exclude tests/docs only
                continue

            # Fetch issue details verbatim
            i_url = f"https://api.github.com/repos/{repo}/issues/{issue_num}"
            r_issue = client.get(i_url)
            if r_issue.status_code == 403 or r_issue.status_code == 429:
                print(f"LOOKUP FAILED: Rate limit exceeded on {i_url}. Status {r_issue.status_code}")
                sys.exit(1)
            if r_issue.status_code != 200:
                continue

            issue_data = r_issue.json()
            if "pull_request" in issue_data:
                # was a PR, not an issue
                continue

            case_entry = {
                "id": f"{repo.split('/')[1]}-{issue_num}",
                "repo": repo,
                "issue_url": f"https://github.com/{repo}/issues/{issue_num}",
                "pr_url": pr["html_url"],
                "base_commit_sha": base_sha,
                "title": issue_data["title"],
                "body": issue_data.get("body") or "",
                "changed_files": changed_files,
            }
            cases.append(case_entry)
            print(f"Collected case: {case_entry['id']} (PR #{pr_num} -> Issue #{issue_num}) Base: {base_sha[:8]}")

            if len(raw_samples) < 3:
                raw_samples.append({
                    "case_id": case_entry["id"],
                    "issue_api_sample": {
                        "url": issue_data["url"],
                        "title": issue_data["title"],
                        "state": issue_data["state"],
                        "body_preview": (issue_data.get("body") or "")[:150],
                    },
                    "pr_api_sample": {
                        "url": pr["url"],
                        "base_sha": base_sha,
                        "files": changed_files,
                    }
                })

            if len([c for c in cases if c["repo"] == repo]) >= 8:
                break
        page += 1

print(f"\nTotal cases collected: {len(cases)}")
with open(REPO_ROOT / "data" / "eval_cases.json", "w", encoding="utf-8") as f:
    json.dump({"retrieval": cases, "qa": []}, f, indent=2)

with open(REPO_ROOT / "data" / "raw_api_samples.json", "w", encoding="utf-8") as f:
    json.dump(raw_samples, f, indent=2)

print("Saved to data/eval_cases.json and data/raw_api_samples.json")
