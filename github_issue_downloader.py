import requests
import json
import os
import time
from urllib.parse import urlparse

class GitHubIssuesDownloader:
    def __init__(self, token=None):
        """Initialize the downloader with optional GitHub token."""
        self.headers = {}
        if token:
            self.headers = {'Authorization': f'token {token}'}
        self.base_url = "https://api.github.com"

    def extract_repo_info(self, github_url):
        """Extract owner and repo name from GitHub URL."""
        path_parts = urlparse(github_url).path.strip('/').split('/')
        if len(path_parts) >= 2:
            return path_parts[0], path_parts[1]
        return None, None

    def get_all_issues(self, owner, repo):
        """Download all issues for a repository including closed ones."""
        issues = []
        page = 1
        per_page = 100

        while True:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues"
            params = {
                'state': 'all',
                'per_page': per_page,
                'page': page
            }

            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                batch = response.json()
                if not batch:
                    break

                issues.extend(batch)
                page += 1

                # Handle GitHub API rate limiting
                if 'X-RateLimit-Remaining' in response.headers:
                    remaining = int(response.headers['X-RateLimit-Remaining'])
                    if remaining <= 1:
                        reset_time = int(response.headers['X-RateLimit-Reset'])
                        sleep_time = reset_time - time.time() + 1
                        if sleep_time > 0:
                            print(f"Rate limit reached. Sleeping for {sleep_time:.0f} seconds...")
                            time.sleep(sleep_time)

            except requests.exceptions.RequestException as e:
                print(f"Error downloading issues for {owner}/{repo}: {str(e)}")
                return None

            # Small delay to be nice to GitHub's API
            time.sleep(0.5)

        return issues

    def save_issues(self, issues, owner, repo, output_dir="issues"):
        """Save issues to a JSON file."""
        if issues is None:
            return False

        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"{owner}_{repo}_issues.json")

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(issues, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving issues for {owner}/{repo}: {str(e)}")
            return False

def main():
    # Create output directory
    output_dir = "github_issues"
    os.makedirs(output_dir, exist_ok=True)

    # Initialize downloader
    # If you have a GitHub token, pass it to the constructor
    token = "ADD YOUR TOKEN HERE"
    downloader = GitHubIssuesDownloader(token)

    # Read URLs from file
    try:
        with open('urls.txt', 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
    except IOError as e:
        print(f"Error reading urls.txt: {str(e)}")
        return

    # Process each repository
    for url in urls:
        owner, repo = downloader.extract_repo_info(url)
        if not owner or not repo:
            print(f"Invalid GitHub URL: {url}")
            continue

        print(f"Downloading issues for {owner}/{repo}...")
        issues = downloader.get_all_issues(owner, repo)

        if issues is not None:
            if downloader.save_issues(issues, owner, repo, output_dir):
                print(f"Successfully saved {len(issues)} issues for {owner}/{repo}")
            else:
                print(f"Failed to save issues for {owner}/{repo}")

if __name__ == "__main__":
    main()
