import os
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import platform
from collections import defaultdict
import json
from datetime import datetime
import statistics

# Get the current user's username and create a temporary folder in /tmp/
user_name = os.getlogin()
temp_dir = os.path.join('/tmp', user_name)

# Create the temp directory if it doesn't exist
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

urls = []
with open("urls.txt", "r") as file:
    for line in file:
        urls.append(line.strip("\n"))

# Function to clone a repository
def clone_repo(repo_name):
    repo_base_name = repo_name.rstrip('/').split('/')[-1]
    repo_url = f"{repo_name}.git"
    repo_dir = os.path.join(temp_dir, repo_base_name)

    if not os.path.exists(repo_dir):
        print(f"Cloning {repo_url} into {repo_dir}...")
        try:
            process = subprocess.Popen(['git', 'clone', repo_url, repo_dir],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       universal_newlines=True,
                                       encoding='utf-8')
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                print(f"Failed to clone {repo_url}: {stderr}")
                return None
            return repo_dir
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone {repo_url}: {e}")
            return None
        except UnicodeDecodeError as e:
            print(f"Encoding error when cloning repository: {e}")
            return None
    else:
        print(f"Repository {repo_base_name} already cloned.")
        return repo_dir

# Function to run scc and save the output to a JSON file
def run_scc(repo_dir):
    repo_name = os.path.basename(repo_dir)
    scc_output = f"{repo_name}_scc_output.json"

    if platform.system() == "Windows":
        scc_cmd = 'scc.exe'
    else:
        scc_cmd = './scc'

    try:
        print(f"Running scc on {repo_dir}...")
        with open(scc_output, 'w') as output_file:
            subprocess.run([scc_cmd, '--format', 'json', repo_dir], stdout=output_file, check=True)

        with open(scc_output, 'r') as f:
            scc_data = json.load(f)

        return scc_data
    except subprocess.CalledProcessError as e:
        print(f"Failed to analyze {repo_name} with scc: {e}")
        return None

# Function to run RefactoringMiner
def run_refactoringminer(repo_dir):
    repo_name = os.path.basename(repo_dir)
    json_output = f"{repo_name}_refactorings.json"

    if platform.system() == "Windows":
        refactoringminer_cmd = os.path.join(os.path.dirname(__file__), 'RefactoringMiner.bat')
    else:
        refactoringminer_cmd = os.path.join(os.path.dirname(__file__), 'RefactoringMiner')

    # Check if RefactoringMiner executable exists
    if not shutil.which(refactoringminer_cmd):
        print(f"RefactoringMiner executable not found. Please ensure it's in your PATH or in the current directory.")
        return None

    try:
        print(f"Running RefactoringMiner on {repo_dir}...")
        process = subprocess.Popen([refactoringminer_cmd, '-a', repo_dir, '-json', json_output],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   universal_newlines=True,
                                   encoding='utf-8')
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"RefactoringMiner failed with error: {stderr}")
            return None

        if not os.path.exists(json_output):
            print(f"RefactoringMiner did not produce the expected output file: {json_output}")
            return None

        return json_output
    except subprocess.CalledProcessError as e:
        print(f"Failed to analyze {repo_name} with RefactoringMiner: {e}")
        return None
    except FileNotFoundError:
        print(f"RefactoringMiner executable not found. Please ensure it's in your PATH or in the current directory.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while running RefactoringMiner: {e}")
        return None

# Function to process RefactoringMiner output
def process_refactoring_miner_output(json_output):
    with open(json_output, 'r') as f:
        refactoring_data = json.load(f)

    refactorings = defaultdict(lambda: defaultdict(int))
    refactoring_timestamps = defaultdict(list)

    for commit in refactoring_data.get('commits', []):
        author = commit.get('author', 'Unknown')  # Use 'Unknown' if author is not present
        timestamp_str = commit.get('date')
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.rstrip('Z'))
            except ValueError:
                print(f"Invalid timestamp format: {timestamp_str}")
                continue
        else:
            print(f"Missing timestamp for commit: {commit.get('sha1', 'Unknown SHA')}")
            continue

        for refactoring in commit.get('refactorings', []):
            refactoring_type = refactoring.get('type', 'Unknown')
            refactorings[author][refactoring_type] += 1
            refactoring_timestamps[refactoring_type].append(timestamp)

    # Calculate average inter-refactoring periods
    avg_periods = {}
    for refactoring_type, timestamps in refactoring_timestamps.items():
        if len(timestamps) > 1:
            sorted_timestamps = sorted(timestamps)
            periods = [(sorted_timestamps[i+1] - sorted_timestamps[i]).total_seconds() / 3600
                       for i in range(len(sorted_timestamps)-1)]
            avg_periods[refactoring_type] = statistics.mean(periods)
        else:
            avg_periods[refactoring_type] = None

    return refactorings, avg_periods

# Function to run git log
def run_git_log(repo_dir):
    git_log_command = [
        'git', '-C', repo_dir, 'log', '--numstat', '--pretty=format:%H,%an'
    ]
    try:
        print(f"Running git log on {repo_dir}...")

        # Run the git log command and capture the output
        process = subprocess.Popen(git_log_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8')
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"Error running git log: {stderr}")
            return []

        # Split the output by lines
        git_log_data = stdout.splitlines()

        return git_log_data  # This will be a list of lines for processing

    except subprocess.CalledProcessError as e:
        print(f"Failed to retrieve git log for {repo_dir}: {e}")
        print(f"Error output: {e.stderr}")
        return []
    except UnicodeDecodeError as e:
        print(f"Encoding error when reading git log output: {e}")
        return []

# Function to collect TLOC for each developer and tie it to refactorings
def collect_developer_tloc(scc_data, git_log_data, refactorings):
    developer_tloc = defaultdict(lambda: defaultdict(int))
    file_tloc = defaultdict(int)
    refactoring_tloc = defaultdict(lambda: defaultdict(int))

    commit_hash = None
    author = None

    for entry in git_log_data:
        if ',' in entry:
            parts = entry.split(",")
            commit_hash = parts[0]
            author = ",".join(parts[1:])
        else:
            if not entry or "\t" not in entry:
                continue

            try:
                added, removed, filename = entry.split("\t")
                if added == '-' or removed == '-':
                    total_touched = 0
                else:
                    total_touched = int(added) + int(removed)

                developer_tloc[author][filename] += total_touched
                file_tloc[filename] += total_touched
            except ValueError:
                continue

    # Update TLOC with scc data
    for file_info in scc_data:
        filename = file_info.get("Filename", "unknown")
        code_lines = file_info.get("Code", 0)
        file_tloc[filename] = max(file_tloc[filename], code_lines)

    # Adjust developer TLOC based on file TLOC
    for author, files in developer_tloc.items():
        for filename, tloc in files.items():
            developer_tloc[author][filename] = min(tloc, file_tloc[filename])

    # Tie TLOC to refactorings
    for author, refactoring_types in refactorings.items():
        for refactoring_type, count in refactoring_types.items():
            refactoring_tloc[author][refactoring_type] = sum(developer_tloc[author].values()) / len(refactoring_types)

    return developer_tloc, refactoring_tloc

# Function to delete a repository folder
def delete_repo(repo_dir):
    try:
        shutil.rmtree(repo_dir)
        print(f"Deleted repository at {repo_dir}")
    except Exception as e:
        print(f"Failed to delete {repo_dir}: {e}")

# Function to clone, analyze (RefactoringMiner & scc), and delete the repository
def clone_analyze_delete(repo_name):
    repo_dir = clone_repo(repo_name)
    if repo_dir:
        scc_data = run_scc(repo_dir)
        git_log_data = run_git_log(repo_dir)

        refminer_output = run_refactoringminer(repo_dir)
        if refminer_output:
            refactorings, avg_periods = process_refactoring_miner_output(refminer_output)
            developer_tloc, refactoring_tloc = collect_developer_tloc(scc_data, git_log_data, refactorings)

            result = {
                "refactorings": dict(refactorings),
                "avg_inter_refactoring_periods": avg_periods,
                "developer_tloc": dict(developer_tloc),
                "refactoring_tloc": dict(refactoring_tloc)
            }

            with open(f"{os.path.basename(repo_dir)}_analysis.json", 'w') as f:
                json.dump(result, f, indent=2)

            print(f"Analysis results saved for {repo_name}")

        delete_repo(repo_dir)
    return f"Finished processing {repo_name}"

# Parallelize cloning, analyzing (RefactoringMiner & scc), and deleting with ThreadPoolExecutor
def parallel_clone_analyze_delete(urls, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(clone_analyze_delete, url) for url in urls]

        # As tasks are completed, print their result
        for future in as_completed(futures):
            print(future.result())

# Set the number of workers (threads) and run the analysis
if __name__ == "__main__":
    parallel_clone_analyze_delete(urls, max_workers=1)