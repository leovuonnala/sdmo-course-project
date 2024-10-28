# sdmo-course-project
Course project for Software Development, Maintenance and Operations

## How to use it:
Main.py is the repo downloader. It needs RefactoringMiner and scc to function. Main.py should be placed in the root of the project. RefactoringMiner's lib and bin folders should be placed in the same folder. SCC executable must be placed in bin. 
INCREASE ulimit -n to unlimited, otherwise RefactoringMiner WILL CRASH on Linux. https://ss64.com/bash/ulimit.html
1. Create a venv, install pydriller.
2. Place urls.txt in the same folder as main.py
3. Run python3 main.py
4. Wait. Massive repos like Apaches Camel take forever to analyse. (On a 6-core coffee lake machine with 16 gigabytes of ram, of which 14 gigabytes were allocated to Java, analysing Apache Camel took 2.5 days.)

If you want to mine Jira issue data, use jirascraper.py. It needs a venv and pip install selenium. The script is hardcoded to use Chrome. It should be trivial to modify if firefox compatibility is needed. Chromedriver location is also hardcoded to be /usr/bin/chromedriver. Change this if needed.
Jirascraper will use all available cores for scraping. If you do not want that to happen, modify line 397 (num_cores). It expects the urls to be in a file called "jira_urls.txt". This can be modified by renaming the file name on line 389.

Github_issue_downloader.py needs a classic personal access token with repo scope for issue downloading. If you do not have it, modify line 90 from "downloader = GitHubIssuesDownloader(token)" to "downloader = GitHubIssuesDownloader()" Note that not providing a token causes the downloader to be subjected to rate limits.

software used:

RefactoringMiner by Nikolaos Tsantalis, Matin Mansouri, Laleh Eshkevari, Davood Mazinanian, and Danny Dig

https://github.com/tsantalis/RefactoringMiner

scc

https://github.com/boyter/scc

Pydriller

Selenium, chromewebdriver
