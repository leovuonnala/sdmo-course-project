import subprocess
import requests
import os
import json

import shutil
import sys

from pydriller import Repository

# GitHub API base URL and access token
BASE_URL = "https://api.github.com"
TOKEN = "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"
HEADERS = {"Authorization": f"token {TOKEN}"}



# Path to tools
REFACTORING_MINER_PATH = "RefactoringMiner"  # Adjust as needed
SCC_PATH = "scc"  # Adjust as needed

def get_script_dir():
    return os.path.dirname(os.path.realpath(sys.argv[0]))

def find_executable(name):
    script_dir = get_script_dir()
    local_path = os.path.join(script_dir, name)

    if os.name == "nt":
        local_path += ".exe"

    if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
        return local_path

    return shutil.which(name)

def clone_repo(url, repo_path):
    if os.path.exists(repo_path):
        print(f"Removing existing repository at {repo_path}")
        shutil.rmtree(repo_path)

    print(f"Cloning repository: {url}")
    try:
        subprocess.run(["git", "clone", url, repo_path], check=True)

        # Check what files were cloned
        print(f"Files in {repo_path}: {os.listdir(repo_path)}")

        # Verify the `.git` directory exists
        git_dir = os.path.join(repo_path, ".git")
        if os.path.exists(git_dir):
            print(f"Repository cloned successfully: {repo_path}")
            return True
        else:
            print(f"Cloning failed: .git directory not found in {repo_path}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while cloning repository {url}: {e}")
        return False

def run_refactoring_miner(repo_path, output_file):
    refactoring_miner_path = find_executable(REFACTORING_MINER_PATH)
    if not refactoring_miner_path:
        print(f"RefactoringMiner not found. Please ensure it's in the script directory or system PATH.")
        return False

    command = [
        refactoring_miner_path,
        "-a",  # Analyze entire repository
        repo_path,
        "-json",
        output_file
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"RefactoringMiner failed: {result.stderr}")
        return False
    print(f"RefactoringMiner analysis saved to {output_file}")
    return True

def run_scc_on_commit(repo_path, commit_hash):
    scc_path = find_executable(SCC_PATH)
    if not scc_path:
        print(f"SCC not found. Please ensure it's in the script directory or system PATH.")
        return {}

    # Get the diff for the commit
    diff_output = subprocess.run(["git", "show", commit_hash], cwd=repo_path, capture_output=True, text=True).stdout

    # Create a temporary directory for the changed files
    temp_dir = os.path.join(repo_path, "temp")
    os.makedirs(temp_dir, exist_ok=True)  # Ensure the temp directory exists

    current_file = None
    current_content = []
    for line in diff_output.split('\n'):
        if line.startswith("diff --git"):
            if current_file:
                # Ensure the directory for the current file exists
                current_file_dir = os.path.dirname(os.path.join(temp_dir, current_file))
                os.makedirs(current_file_dir, exist_ok=True)  # Create directories if missing

                with open(os.path.join(temp_dir, current_file), 'w') as f:
                    f.write('\n'.join(current_content))

            current_file = line.split()[-1].lstrip('b/')
            current_content = []
        elif line.startswith("+") and not line.startswith("+++"):
            current_content.append(line[1:])

    # Write the last file if it exists
    if current_file:
        current_file_dir = os.path.dirname(os.path.join(temp_dir, current_file))
        os.makedirs(current_file_dir, exist_ok=True)  # Create directories if missing

        with open(os.path.join(temp_dir, current_file), 'w') as f:
            f.write('\n'.join(current_content))

    # Run SCC on the temporary directory
    scc_output = subprocess.run([scc_path, temp_dir, "--format", "json"], capture_output=True, text=True).stdout

    # Clean up the temporary directory
    shutil.rmtree(temp_dir)

    return json.loads(scc_output)


def analyze_commits_with_pydriller(repo_path, refactoring_data):
    repo = Repository(repo_path)
    commit_analysis = []

    for commit in repo.traverse_commits():
        if commit.hash not in refactoring_data:
            continue  # Skip commits not in refactoring data

        scc_data = run_scc_on_commit(repo_path, commit.hash)
        commit_diff = {
            "hash": commit.hash,
            "author": commit.author.name,
            "date": commit.committer_date.isoformat(),
            "message": commit.msg,
            "refactorings": refactoring_data[commit.hash].get("refactorings", []),
            "scc_analysis": scc_data,
            "diff_info": {
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
                ],
            }
        }
        commit_analysis.append(commit_diff)

    return commit_analysis

def process_repo(url):
    repo_name = url.split('/')[-1]
    repo_path = os.path.join(get_script_dir(), "repos", repo_name)

    if not clone_repo(url, repo_path):
        print(f"Skipping repository {repo_name} due to cloning failure.")
        return

    # Run RefactoringMiner and store output
    refactoring_output_file = os.path.join(repo_path, "refactoring_output.json")
    if not run_refactoring_miner(repo_path, refactoring_output_file):
        print(f"Skipping {repo_name} due to RefactoringMiner failure.")
        return

    # Load RefactoringMiner output
    with open(refactoring_output_file, 'r') as f:
        refactoring_data = json.load(f)['commits']

    # Analyze commits with PyDriller and SCC
    commit_analysis = analyze_commits_with_pydriller(repo_path, {commit['sha1']: commit for commit in refactoring_data})

    # Save analysis to JSON file
    analysis_output_file = os.path.join(repo_path, f"{repo_name}_analysis.json")
    with open(analysis_output_file, "w") as f:
        json.dump(commit_analysis, f, indent=2)

    print(f"Analysis saved to {analysis_output_file}")

def process_all_repos():
    script_dir = get_script_dir()
    urls_file = os.path.join(script_dir, "urls.txt")

    # Read URLs from the file
    with open(urls_file, "r") as f:
        repo_urls = [line.strip() for line in f.readlines()]

    for url in repo_urls:
        if url:
            print(f"Processing repository: {url}")
            process_repo(url)

if __name__ == "__main__":
    process_all_repos()
    print("All repositories processed.")
