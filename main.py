import os
import subprocess
import json
import requests
import time
import shutil
from pydriller import Repository
import concurrent.futures
import threading

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

def read_urls(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def clone_repo(url, target_dir):
    repo_name = url.split('/')[-1]
    target_path = os.path.join(target_dir, repo_name)
    if not os.path.exists(target_path):
        subprocess.run(['git', 'clone', url, target_path], check=True)
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

def get_main_branch(repo_path):
    for branch in ['main', 'master']:
        try:
            subprocess.run(['git', 'checkout', branch], cwd=repo_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return branch
        except subprocess.CalledProcessError:
            continue
    raise Exception("Neither 'main' nor 'master' branch found")

def get_loc(repo_path, commit_hash):
    subprocess.run(['git', 'checkout', commit_hash], cwd=repo_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    scc_output = subprocess.check_output([os.path.join('bin', 'scc'), '-f', 'json', repo_path], universal_newlines=True)
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

    for commit_info in refactorings_data['commits']:
        commit_hash = commit_info['sha1']

        repo = Repository(repo_path, single=commit_hash)
        for commit in repo.traverse_commits():
            previous_commit_hash = commit.parents[0]
            developer = commit.author.name

            loc_before = get_loc(repo_path, previous_commit_hash)
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

            break  # We only need to process the single commit

    main_branch = get_main_branch(repo_path)
    subprocess.run(['git', 'checkout', main_branch], cwd=repo_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return effort_data

print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def process_repository(url, repos_dir, results_dir):
    repo_path = None
    try:
        repo_path, repo_name = clone_repo(url, repos_dir)

        # Get the main branch right after cloning
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
        # Ensure the repository folder is deleted even if an error occurs
        if repo_path and os.path.exists(repo_path):
            shutil.rmtree(repo_path)
            safe_print(f"Cleaned up repository folder for {url}")

def main():
    urls_file = 'urls.txt'
    repos_dir = 'repos'
    results_dir = 'results'

    os.makedirs(repos_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    urls = read_urls(urls_file)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        futures = [executor.submit(process_repository, url, repos_dir, results_dir) for url in urls]
        concurrent.futures.wait(futures)

    # Clean up the repos directory after all processing is complete
    if os.path.exists(repos_dir):
        shutil.rmtree(repos_dir)
        safe_print(f"Cleaned up {repos_dir} directory.")

if __name__ == "__main__":
    main()
