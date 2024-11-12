import os
import subprocess
import json
#import requests if python complains, remove comment and install requests
#import time
import shutil
from pydriller import Repository
import concurrent.futures
import threading
from urllib.parse import urlparse, urlunparse

# Set of programming languages to consider
PROGRAMMING_LANGUAGES = {
    "FoxPro", "1C:Enterprise", "4th Dimension", "ABAP", "ABC", "ActionScript", "Ada", "Agilent VEE",
    "Algol", "Alice", "Angelscript", "Apex", "APL", "Applescript", "Arc", "AspectJ", "Assembly",
    "ATLAS", "AutoHotkey", "AutoIt", "AutoLISP", "Automator", "Avenue", "Awk", "B4X", "Ballerina",
    "Bash", "Basic", "BBC BASIC", "bc", "BCPL", "BETA", "BlitzMax", "Boo", "Bourne shell", "Brainfuck",
    "C shell", "C#", "C++", "C++/CLI", "C-Omega", "C", "Caml", "Carbon", "Ceylon", "CFML", "cg", "Ch",
    "Chapel", "CHILL", "CIL", "Citrine", "CL", "Clarion", "Clean", "Clipper", "CLIPS", "Clojure", "CLU",
    "COBOL", "Cobra", "CoffeeScript", "COMAL", "Common Lisp", "CORAL 66", "Crystal", "cT", "Curl", "D",
    "Dart", "DCL", "Delphi", "DiBOL", "Dylan", "E", "ECMAScript", "EGL", "Eiffel", "Elixir", "Elm",
    "Emacs Lisp", "Emerald", "Erlang", "Etoys", "Euphoria", "EXEC", "F#", "Factor", "Falcon", "Fantom",
    "Felix", "Forth", "Fortran", "Fortress", "FreeBASIC", "Gambas", "GAMS", "GLSL", "GML", "GNU Octave",
    "Go", "Gosu", "Groovy", "Hack", "Harbour", "Haskell", "Haxe", "Heron", "HPL", "HyperTalk", "Icon",
    "IDL", "Idris", "Inform", "Informix-4GL", "INTERCAL", "Io", "Ioke", "J#", "J", "JADE", "Java",
    "JavaFX Script", "JavaScript", "JScript", "JScript.NET", "Julia", "Korn shell", "Kotlin", "LabVIEW",
    "Ladder Logic", "Lasso", "Limbo", "Lingo", "Lisp", "LiveCode", "Logo", "LotusScript", "LPC", "Lua",
    "Lustre", "M4", "MAD", "Magic", "Magik", "Malbolge", "MANTIS", "Maple", "MATLAB", "Max/MSP",
    "MAXScript", "MDX", "MEL", "Mercury", "Miva", "ML", "Modula-2", "Modula-3", "Mojo", "Monkey", "MOO",
    "Moto", "MQL5", "MS-DOS batch", "MUMPS", "NATURAL", "Nemerle", "NetLogo", "Nim", "Nix", "NQC",
    "NSIS", "NXT-G", "Oberon", "Object Rexx", "Objective-C", "OCaml", "Occam", "OpenCL", "OpenEdge ABL",
    "OPL", "Oxygene", "Oz", "Paradox", "Pascal", "Perl", "PHP", "Pike", "PILOT", "PL/I", "PL/SQL",
    "Pliant", "Pony", "PostScript", "POV-Ray", "PowerBasic", "PowerScript", "PowerShell", "Processing",
    "Programming Without Coding Technology", "Prolog", "Pure Data", "PureBasic", "Python", "Q", "R",
    "Racket", "Raku", "REBOL", "Red", "REXX", "Ring", "RPG", "Ruby", "Rust", "S-PLUS", "S", "SAS",
    "Sather", "Scala", "Scheme", "Scratch", "sed", "Seed7", "SIGNAL", "Simula", "Simulink", "Slate",
    "Small Basic", "Smalltalk", "Smarty", "Snap!", "SNOBOL", "Solidity", "SPARK", "SPSS", "SQL", "SQR",
    "Squeak", "Squirrel", "Standard ML", "Stata", "Structured Text", "Suneido", "SuperCollider", "Swift",
    "SystemVerilog", "TACL", "Tcl", "tcsh", "Tex", "thinBasic", "TOM", "Transact-SQL", "TypeScript",
    "Uniface", "Vala", "VBScript", "VHDL", "Visual Basic", "WebAssembly", "WebDNA", "Whitespace",
    "Wolfram", "X++", "X10", "xBase", "XBase++", "XC", "Xen", "Xojo", "XPL", "XQuery", "XSLT", "Xtend",
    "yacc", "Yorick", "Z shell", "Zig"
}

def create_authenticated_url(url, token):
    """Convert a regular GitHub URL to an authenticated URL with token."""
    parsed = urlparse(url)
    if parsed.hostname and 'github.com' in parsed.hostname:
        netloc = f'{token}@{parsed.hostname}'
        return urlunparse(parsed._replace(netloc=netloc))
    return url

def read_urls(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def clone_repo(url, target_dir, token):
    """Clone repository with authentication token."""
    repo_name = url.split('/')[-1]
    target_path = os.path.join(target_dir, repo_name)

    if not os.path.exists(target_path):
        authenticated_url = create_authenticated_url(url, token)

        # Set up Git configuration for the process
        env = os.environ.copy()
        env['GIT_TERMINAL_PROMPT'] = '0'  # Disable Git credential prompt

        try:
            subprocess.run(
                ['git', 'clone', authenticated_url, target_path],
                check=True,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE  # Capture stderr to avoid exposing token in logs
            )
        except subprocess.CalledProcessError as e:
            # Clean up error message to avoid exposing token
            error_msg = str(e.stderr.decode()).replace(token, '***')
            raise Exception(f"Failed to clone repository: {error_msg}")

    return target_path, repo_name

def run_refactoring_miner(repo_path, output_file):
    refactoring_miner_path = os.path.join('bin', 'RefactoringMiner')
    command = [
        refactoring_miner_path,
        '-a', repo_path,
        '-json', output_file
    ]
    subprocess.run(command, check=True)

def analyze_diffs(repo_path, refactorings_file):
    with open(refactorings_file, 'r') as f:
        refactorings_data = json.load(f)

    output_data = []

    for commit_info in refactorings_data['commits']:
        commit_hash = commit_info['sha1']

        for commit in Repository(repo_path, single=commit_hash).traverse_commits():
            diff_stats = {}
            diff_content = {}

            for file in commit.modified_files:
                diff_stats[file.filename] = {
                    'insertions': file.added_lines,
                    'deletions': file.deleted_lines,
                }
                diff_content[file.filename] = file.diff

            output_data.append({
                'commit_hash': commit_hash,
                'previous_commit_hash': commit.parents[0],
                'diff_stats': diff_stats,
                'diff_content': diff_content
            })

    return output_data

def safe_git_checkout(repo_path, commit_hash):
    """
    Safely checkout a specific commit, handling detached HEAD states.
    Returns True if successful, False otherwise.
    """
    try:
        # First, try to fetch the commit if it's not available
        subprocess.run(
            ['git', 'fetch', '--all', '--prune'],
            cwd=repo_path,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Clean any untracked files and reset any changes
        subprocess.run(
            ['git', 'clean', '-fd'],
            cwd=repo_path,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        subprocess.run(
            ['git', 'reset', '--hard'],
            cwd=repo_path,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Now try to checkout the commit
        subprocess.run(
            ['git', 'checkout', '-f', commit_hash],
            cwd=repo_path,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False

def get_main_branch(repo_path):
    """Modified to be more robust"""
    try:
        # First try to get the default branch from remote
        result = subprocess.run(
            ['git', 'remote', 'show', 'origin'],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )

        for line in result.stdout.split('\n'):
            if 'HEAD branch:' in line:
                default_branch = line.split(':')[1].strip()
                if safe_git_checkout(repo_path, default_branch):
                    return default_branch
    except subprocess.CalledProcessError:
        pass

    # Fallback to checking main/master
    for branch in ['main', 'master']:
        if safe_git_checkout(repo_path, branch):
            return branch

    raise Exception("Could not determine or checkout main branch")

def get_loc(repo_path, commit_hash):
    """Modified to use safe checkout"""
    if not safe_git_checkout(repo_path, commit_hash):
        # If checkout fails, return 0 or raise an exception based on your needs
        return 0

    scc_output = subprocess.check_output(
        [os.path.join('bin', 'scc'), '-f', 'json', repo_path],
        universal_newlines=True
    )
    scc_data = json.loads(scc_output)

    total_loc = 0
    for lang_data in scc_data:
        lang_name = lang_data['Name']
        if any(pl.lower() in lang_name.lower() for pl in PROGRAMMING_LANGUAGES):
            total_loc += lang_data['Code']

    return total_loc

def analyze_developer_effort(repo_path, refactorings_file):
    with open(refactorings_file, 'r') as f:
        refactorings_data = json.load(f)

    effort_data = []

    try:
        for commit_info in refactorings_data['commits']:
            commit_hash = commit_info['sha1']

            repo = Repository(repo_path, single=commit_hash)
            for commit in repo.traverse_commits():
                try:
                    previous_commit_hash = commit.parents[0]
                    developer = commit.author.name

                    # Use safe checkout for both commits
                    if not safe_git_checkout(repo_path, previous_commit_hash):
                        safe_print(f"Warning: Could not checkout {previous_commit_hash}, skipping...")
                        continue

                    loc_before = get_loc(repo_path, previous_commit_hash)

                    if not safe_git_checkout(repo_path, commit_hash):
                        safe_print(f"Warning: Could not checkout {commit_hash}, skipping...")
                        continue

                    loc_after = get_loc(repo_path, commit_hash)
                    tloc = abs(loc_after - loc_before)

                    effort_data.append({
                        'commit_hash': commit_hash,
                        'previous_commit_hash': previous_commit_hash,
                        'developer': developer,
                        'loc_before': loc_before,
                        'loc_after': loc_after,
                        'tloc': tloc
                    })
                except Exception as e:
                    safe_print(f"Warning: Error processing commit {commit_hash}: {str(e)}")
                break  # We only need to process the single commit
    except Exception as e:
        safe_print(f"Warning: Error in analyze_developer_effort: {str(e)}")

    try:
        # Try to return to main branch, but don't fail if we can't
        main_branch = get_main_branch(repo_path)
        safe_git_checkout(repo_path, main_branch)
    except Exception:
        pass

    return effort_data

print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def process_repository(url, repos_dir, results_dir, token):
    repo_path = None
    try:
        repo_path, repo_name = clone_repo(url, repos_dir, token)

        main_branch = get_main_branch(repo_path)

        repo_results_dir = os.path.join(results_dir, repo_name)
        os.makedirs(repo_results_dir, exist_ok=True)

        refactorings_file = os.path.join(repo_results_dir, f'{repo_name}_refactorings.json')
        run_refactoring_miner(repo_path, refactorings_file)

        diff_analysis = analyze_diffs(repo_path, refactorings_file)

        diff_analysis_file = os.path.join(repo_results_dir, f'{repo_name}_diff_analysis.json')
        with open(diff_analysis_file, 'w') as f:
            json.dump(diff_analysis, f, indent=2)

        effort_analysis = analyze_developer_effort(repo_path, refactorings_file)

        effort_analysis_file = os.path.join(repo_results_dir, f'{repo_name}_effort_analysis.json')
        with open(effort_analysis_file, 'w') as f:
            json.dump(effort_analysis, f, indent=2)

        safe_print(f"Processed {repo_name} successfully. Main branch: {main_branch}")
    except subprocess.CalledProcessError as e:
        safe_print(f"Error processing {url}: {e}")
    except Exception as e:
        safe_print(f"Unexpected error processing {url}: {e}")
    finally:
        if repo_path and os.path.exists(repo_path):
            shutil.rmtree(repo_path)
            safe_print(f"Cleaned up repository folder for {url}")

def main():
    urls_file = 'urls.txt'
    repos_dir = 'repos'
    results_dir = 'results'

    # Get token from environment variable for security
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set")

    os.makedirs(repos_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    urls = read_urls(urls_file)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        futures = [
            executor.submit(process_repository, url, repos_dir, results_dir, token)
            for url in urls
        ]
        concurrent.futures.wait(futures)

    if os.path.exists(repos_dir):
        shutil.rmtree(repos_dir)
        safe_print(f"Cleaned up {repos_dir} directory.")

if __name__ == "__main__":
    main()
