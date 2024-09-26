import subprocess
import requests
from pydriller import Repository
import os
import json
import re
from datetime import datetime
import platform
import shutil
import sys

# GitHub API base URL and access token
BASE_URL = "https://api.github.com"
TOKEN = "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"
HEADERS = {"Authorization": f"token {TOKEN}"}


def get_script_dir():
    return os.path.dirname(os.path.realpath(sys.argv[0]))

# Set RefactoringMiner path to be in the same directory as the script
REFACTORING_MINER_PATH = os.path.join(get_script_dir(), "RefactoringMiner")

def find_executable(name):
    script_dir = get_script_dir()
    local_path = os.path.join(script_dir, name)

    if platform.system() == "Windows":
        local_path += ".exe"

    if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
        return local_path

    return shutil.which(name)

def is_issues_enabled(owner, repo):
    url = f"{BASE_URL}/repos/{owner}/{repo}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()["has_issues"]
    return False

def get_all_issues(owner, repo):
    issues = []
    page = 1
    while True:
        url = f"{BASE_URL}/repos/{owner}/{repo}/issues?state=all&page={page}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200 or not response.json():
            break
        issues.extend(response.json())
        page += 1
    return issues

def process_issue_data(issues):
    issue_data_list = []
    for issue in issues:
        issue_data = {
            "number": issue["number"],
            "title": issue["title"],
            "state": issue["state"],
            "created_at": issue["created_at"],
            "closed_at": issue["closed_at"],
            "labels": [label["name"] for label in issue["labels"]]
        }
        issue_data_list.append(issue_data)
    return issue_data_list

def clone_repo(url, repo_path):
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    # Use the token in the clone URL
    token_url = url.replace("https://", f"https://{TOKEN}@")
    subprocess.run(["git", "clone", token_url, repo_path], check=True)

def get_subprocess():
    return subprocess

def run_refactoring_miner(repo_path, output_file):
    if not os.path.isfile(REFACTORING_MINER_PATH):
        raise FileNotFoundError(f"RefactoringMiner executable not found at {REFACTORING_MINER_PATH}")

    command = [
        REFACTORING_MINER_PATH,
        "-a", repo_path,
        "-json", output_file
    ]
    get_subprocess().run(command, check=True)

def analyze_commits(repo_path):
    commits_data = []
    repo = Repository(repo_path)
    for commit in repo.traverse_commits():
        commit_data = {
            "hash": commit.hash,
            "author": commit.author.name,
            "date": commit.committer_date.isoformat(),
            "message": commit.msg,
            "files_changed": len(commit.modified_files),
            "lines_added": sum(file.added_lines for file in commit.modified_files),
            "lines_removed": sum(file.deleted_lines for file in commit.modified_files),
            "file_changes": [
                {
                    "filename": file.filename,
                    "change_type": file.change_type.name,
                    "lines_added": file.added_lines,
                    "lines_removed": file.deleted_lines
                }
                for file in commit.modified_files
            ]
        }
        commits_data.append(commit_data)
    return commits_data

def calculate_tloc(repo_path):
    scc_path = find_executable("scc")
    if not scc_path:
        print("SCC not found. Please ensure it's in the script directory or system PATH.")
        return "SCC not available"

    result = subprocess.run([scc_path, repo_path], capture_output=True, text=True, check=True)
    return result.stdout

def mine_github_data(project_url):
    # Extract owner and repo from the URL
    owner, repo = project_url.split('/')[-2:]
    repo = repo.replace('.git', '')

    repo_path = os.path.join(get_script_dir(), "repos", f"{owner}_{repo}")

    if is_issues_enabled(owner, repo):
        print(f"Project {owner}/{repo} uses GitHub Issues.")
        issues = get_all_issues(owner, repo)
        issue_data_list = process_issue_data(issues)
    else:
        print(f"Project {owner}/{repo} does not use GitHub Issues.")
        issue_data_list = []

    clone_repo(project_url, repo_path)

    commits_data = analyze_commits(repo_path)

    refactoring_json_path = os.path.join(get_script_dir(), f"{owner}_{repo}_refactoring_miner_output.json")
    run_refactoring_miner(repo_path, refactoring_json_path)

    tloc_output = calculate_tloc(repo_path)

    final_data = {
        "project": f"{owner}/{repo}",
        "issues": issue_data_list,
        "commits": commits_data,
        "tloc": tloc_output
    }

    return final_data, owner, repo, refactoring_json_path

def load_urls_from_file(filename):
    with open(filename, 'r') as file:
        return [line.strip() for line in file if line.strip()]

if __name__ == "__main__":
    urls_file = os.path.join(get_script_dir(), "urls.txt")

    if not os.path.exists(urls_file):
        print(f"Error: {urls_file} not found.")
        sys.exit(1)

    urls = load_urls_from_file(urls_file)

    for url in urls:
        print(f"Processing repository: {url}")
        try:
            result, owner, repo, refactoring_json_path = mine_github_data(url)

            # Save the full analysis result to a JSON file
            output_path = os.path.join(get_script_dir(), f"{owner}_{repo}_analysis.json")
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)

            print(f"Analysis complete for {owner}/{repo}.")
            print(f"Full results saved to {output_path}")
            print(f"RefactoringMiner JSON output saved to {refactoring_json_path}")
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")

        print("-" * 50)

    print("All repositories processed.")
