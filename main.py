from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
import json
import re

def setup_driver():
    driver_path = '/usr/bin/chromedriver'
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)
    return driver

def safe_find(driver, by, value):
    try:
        return driver.find_element(by, value).text
    except NoSuchElementException:
        return "Not found"

def scrape_issue(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.ID, "summary-val")))
    except TimeoutException:
        print(f"Timeout waiting for page to load: {url}")
        return None

    issue_data = {
        "url": url,
        "issue_key": safe_find(driver, By.ID, "key-val"),
        "summary": safe_find(driver, By.ID, "summary-val"),
        "status": safe_find(driver, By.ID, "status-val"),
        "resolution": safe_find(driver, By.ID, "resolution-val"),
        "description": safe_find(driver, By.ID, "description-val")
    }

    # Click "All" tab to show all activity data
    try:
        all_tab = wait.until(EC.element_to_be_clickable((By.ID, "all-tabpanel")))
        all_tab.click()
        # Wait for the content to load
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "issue-data-block")))
    except TimeoutException:
        print(f"Timeout waiting for 'All' tab on {url}")

    # Scrape mod-content data
    issue_data["mod_content"] = safe_find(driver, By.CLASS_NAME, "mod-content")

    # Scrape issuePanelWrapper data
    issue_data["issue_panel_wrapper"] = safe_find(driver, By.CLASS_NAME, "issuePanelWrapper")

    # Scrape issue_actions_container data
    issue_data["issue_actions"] = []
    try:
        issue_actions_container = driver.find_element(By.ID, "issue_actions_container")
        action_items = issue_actions_container.find_elements(By.CLASS_NAME, "issue-data-block")
        for item in action_items:
            action_data = {
                "type": item.get_attribute("id"),
                "content": item.text
            }
            issue_data["issue_actions"].append(action_data)
    except NoSuchElementException:
        pass

    # Scrape comments
    comments = []
    comment_elements = driver.find_elements(By.CSS_SELECTOR, ".activity-comment")
    for comment in comment_elements:
        try:
            author = comment.find_element(By.CSS_SELECTOR, ".user-hover").text
            date = comment.find_element(By.CSS_SELECTOR, ".date").get_attribute("title")
            content = comment.find_element(By.CSS_SELECTOR, ".action-body").text
            comments.append({"author": author, "date": date, "content": content})
        except NoSuchElementException:
            continue

    issue_data["comments"] = comments
    return issue_data

def get_project_info(url):
    match = re.search(r'/projects/(\w+)/issues/(\w+-(\d+))', url)
    if match:
        return match.group(1), match.group(2), int(match.group(3))
    return None, None, None

def scrape_project(driver, start_url):
    project, _, start_number = get_project_info(start_url)
    if not project or not start_number:
        print(f"Invalid URL format: {start_url}")
        return []

    project_data = []
    current_number = start_number

    while current_number > 0:
        url = f"https://issues.apache.org/jira/browse/{project}-{current_number}"
        print(f"Scraping: {url}")
        issue_data = scrape_issue(driver, url)
        if issue_data:
            project_data.append(issue_data)
        else:
            print(f"Failed to scrape issue {project}-{current_number}")

        current_number -= 1
        time.sleep(1)  # Be nice to the server

    return project_data

def main():
    driver = setup_driver()

    try:
        with open('jira_urls.txt', 'r') as file:
            start_urls = [line.strip() for line in file if line.strip()]

        for start_url in start_urls:
            project, _, _ = get_project_info(start_url)
            if project:
                print(f"Starting project: {project}")
                project_data = scrape_project(driver, start_url)

                # Save project data to a JSON file
                filename = f"{project}_issues_data.json"
                with open(filename, 'w') as f:
                    json.dump(project_data, f, indent=4)

                print(f"Data for project {project} has been saved to {filename}")
            else:
                print(f"Skipping invalid URL: {start_url}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

    print("Data collection complete.")
    print("Individual JSON files have been created for each project.")

if __name__ == "__main__":
    main()