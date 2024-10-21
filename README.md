# sdmo-course-project
Course project for Software Development, Maintenance and Operations

## How to use it:
Main.py is the repo downloader. It needs RefactoringMiner and scc to function. Main.py should be placed in the root of the project. RefactoringMiner's lib and bin folders should be placed in the same folder. SCC executable must be placed in bin. 

1. Create a venv, install pydriller.
2. Place urls.txt in the same folder as main.py
3. Run python3 main.py
4. Wait. Massive repos like Apaches Camel take forever to analyse.

If you want to mine Jira issue data, use webscraper.py. It needs a venv and pip install selenium. The script is hardcoded to use Chrome for ease of development. It should be trivial to modify if firefox compatibility is needed. Chromedriver location is also hardcoded to be /usr/bin/chromedriver. Change this if needed.


software used:

RefactoringMiner by Nikolaos Tsantalis, Matin Mansouri, Laleh Eshkevari, Davood Mazinanian, and Danny Dig

https://github.com/tsantalis/RefactoringMiner

scc

https://github.com/boyter/scc

Pydriller

Selenium, chromewebdriver
