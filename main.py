import os
import subprocess
import shutil  # Required for deleting directories
import pydriller
from concurrent.futures import ThreadPoolExecutor, as_completed

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
            subprocess.run(['git', 'clone', repo_url, repo_dir], check=True)
            return repo_dir
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone {repo_url}: {e}")
            return None
    else:
        print(f"Repository {repo_base_name} already cloned.")
        return repo_dir

# Function to run RefactoringMiner
def run_refactoringminer(repo_dir):
    repo_name = os.path.basename(repo_dir)
    json_output = f"{repo_name}.json"
    try:
        print(f"Running RefactoringMiner on {repo_dir}...")
        subprocess.run(['./RefactoringMiner', '-a', repo_dir, '-json', json_output], check=True)
        return f"Successfully analyzed {repo_name} with RefactoringMiner, results in {json_output}"
    except subprocess.CalledProcessError as e:
        return f"Failed to analyze {repo_name} with RefactoringMiner: {e}"

# Function to run scc and save the output to a text file
def run_scc(repo_dir):
    repo_name = os.path.basename(repo_dir)
    scc_output = f"{repo_name}_scc_output.txt"
    try:
        print(f"Running scc on {repo_dir}...")
        with open(scc_output, 'w') as output_file:
            subprocess.run(['./scc', repo_dir], stdout=output_file, check=True)
        return f"Successfully analyzed {repo_name} with scc, results in {scc_output}"
    except subprocess.CalledProcessError as e:
        return f"Failed to analyze {repo_name} with scc: {e}"

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
        scc_result = run_scc(repo_dir)
        print(scc_result)

        refminer_result = run_refactoringminer(repo_dir)
        print(refminer_result)

        # Delete the repository folder after analysis
        delete_repo(repo_dir)
    return f"Finished processing {repo_name}"

# Parallelize cloning, analyzing (RefactoringMiner & scc), and deleting with ThreadPoolExecutor
def parallel_clone_analyze_delete(urls, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(clone_analyze_delete, url) for url in urls]

        # As tasks are completed, print their result
        for future in as_completed(futures):
            print(future.result())

# Set the number of workers (threads)
# Too many workers will kill your machine (until OOM-killer kills the memory hogs)
parallel_clone_analyze_delete(urls, max_workers=2)
