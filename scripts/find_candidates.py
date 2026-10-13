import subprocess
import re

CLOSING_PATTERN = re.compile(r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:https?://github\.com/[^/]+/[^/]+/issues/|#)(\d+)', re.IGNORECASE)
PR_NUM_PATTERN = re.compile(r'Merge pull request #(\d+)|#(\d+)\)', re.IGNORECASE)

def find_pr_candidates(repo_name, repo_dir):
    # Get last 200 commits with full commit message
    cmd = ['git', 'log', '-n', '200', '--format=---COMMIT---%n%H%n%P%n%s%n%b']
    out = subprocess.check_output(cmd, cwd=repo_dir, text=True)
    chunks = out.split('---COMMIT---\n')[1:]
    
    candidates = []
    seen_issues = set()
    
    for chunk in chunks:
        lines = chunk.strip().split('\n')
        if len(lines) < 3:
            continue
        commit_sha = lines[0].strip()
        parents = lines[1].strip().split()
        subject = lines[2].strip()
        body = '\n'.join(lines[3:])
        full_msg = f"{subject}\n{body}"
        
        # Look for PR number
        pr_match = PR_NUM_PATTERN.search(full_msg)
        if not pr_match:
            continue
        pr_num = int(pr_match.group(1) or pr_match.group(2))
        
        # Look for closing issue
        close_match = CLOSING_PATTERN.search(full_msg)
        if not close_match:
            continue
        issue_num = int(close_match.group(1))
        if issue_num in seen_issues or issue_num == pr_num:
            continue
            
        # Get base sha
        if len(parents) == 2:
            base_sha = parents[0]
        elif len(parents) == 1:
            base_sha = parents[0]
        else:
            continue
            
        seen_issues.add(issue_num)
        candidates.append({
            "repo": repo_name,
            "pr_num": pr_num,
            "issue_num": issue_num,
            "base_sha": base_sha,
            "commit_sha": commit_sha
        })
    return candidates

if __name__ == "__main__":
    for repo_name, repo_dir in [
        ("sherlock-project/sherlock", "cloned_repos/sherlock"),
        ("pallets/click", "cloned_repos/click"),
        ("pallets/werkzeug", "cloned_repos/werkzeug"),
    ]:
        cands = find_pr_candidates(repo_name, repo_dir)
        print(f"{repo_name}: found {len(cands)} candidates")
        for c in cands[:5]:
            print(f"  PR #{c['pr_num']} -> Issue #{c['issue_num']} (base {c['base_sha'][:8]})")
