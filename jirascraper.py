from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
import time
import json
import re
import multiprocessing
from multiprocessing import Pool
import os

def setup_driver():
    driver_path = '/usr/bin/chromedriver'
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)
    return driver

def safe_find(driver, by, value, retries=3):
    for attempt in range(retries):
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((by, value))
            )
            return element.text
        except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
            if attempt == retries - 1:
                return "Not found"
            time.sleep(1)

def click_with_retry(driver, element, retries=3):
    for attempt in range(retries):
        try:
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element))
            element.click()
            return True
        except (StaleElementReferenceException, TimeoutException):
            if attempt == retries - 1:
                return False
            time.sleep(1)
    return False

def get_element_with_retry(driver, by, value, retries=3):
    for attempt in range(retries):
        try:
            return WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((by, value))
            )
        except (StaleElementReferenceException, TimeoutException):
            if attempt == retries - 1:
                raise
            time.sleep(1)

def scrape_linking_module(driver):
    linking_data = {
        "content": "",
        "links": [],
        "links_to": [],
        "mentioned_in": []
    }

    try:
        # First check if linking module exists
        try:
            linking_module = driver.find_element(By.ID, "linkingmodule")
        except NoSuchElementException:
            return None  # Return None if no linking module exists

        # If we get here, the linking module exists, so use get_element_with_retry for better reliability
        linking_module = get_element_with_retry(driver, By.ID, "linkingmodule")

        # Get the full content text from mod-content
        mod_content = linking_module.find_element(By.CLASS_NAME, "mod-content")
        linking_data["content"] = mod_content.text

        try:
            # Find all issue links
            paragraphs = mod_content.find_elements(By.TAG_NAME, "p")

            for p in paragraphs:
                try:
                    link_data = {}

                    # Get the issue type image info
                    try:
                        issue_type_img = p.find_element(By.TAG_NAME, "img")
                        link_data["issue_type"] = {
                            "title": issue_type_img.get_attribute("title"),
                            "icon_url": issue_type_img.get_attribute("src")
                        }
                    except NoSuchElementException:
                        pass

                    # Get the issue link and summary
                    try:
                        link_span = p.find_element(By.CSS_SELECTOR, "span[title]")
                        link_element = link_span.find_element(By.CSS_SELECTOR, "a.issue-link")
                        summary_span = link_span.find_element(By.CLASS_NAME, "link-summary")

                        link_data.update({
                            "key": link_element.get_attribute("data-issue-key"),
                            "url": link_element.get_attribute("href"),
                            "summary": summary_span.text
                        })
                    except NoSuchElementException:
                        continue

                    # Get the status information from the following ul
                    try:
                        snapshot = p.find_element(By.XPATH, "following-sibling::ul[contains(@class, 'link-snapshot')]")

                        # Get priority
                        try:
                            priority_img = snapshot.find_element(By.CSS_SELECTOR, "li.priority img")
                            link_data["priority"] = {
                                "title": priority_img.get_attribute("title"),
                                "icon_url": priority_img.get_attribute("src")
                            }
                        except NoSuchElementException:
                            pass

                        # Get status
                        try:
                            status_span = snapshot.find_element(By.CSS_SELECTOR, "li.status span.jira-issue-status-lozenge")
                            link_data["status"] = {
                                "text": status_span.text,
                                "tooltip": status_span.get_attribute("data-tooltip")
                            }
                        except NoSuchElementException:
                            pass

                    except NoSuchElementException:
                        pass

                    if link_data:  # Only append if we found some data
                        linking_data["links"].append(link_data)

                except (NoSuchElementException, StaleElementReferenceException):
                    continue

            # Function to scrape remote links (used for both "links to" and "mentioned in")
            def scrape_remote_links(dt_title):
                remote_links_data = []
                try:
                    dt_element = mod_content.find_element(By.CSS_SELECTOR, f"dt[title='{dt_title}']")
                    remote_links = dt_element.find_elements(By.XPATH, "following-sibling::dd[contains(@class, 'remote-link')]")

                    for remote_link in remote_links:
                        try:
                            link_data = {
                                "remote_link_id": remote_link.get_attribute("data-remote-link-id"),
                                "requires_async": "data-requires-async-loading" in remote_link.get_attribute("class")
                            }

                            # Get the link content
                            link_content = remote_link.find_element(By.CLASS_NAME, "link-content")

                            # Get favicon and link details from paragraph
                            try:
                                p_element = link_content.find_element(By.TAG_NAME, "p")
                                favicon = p_element.find_element(By.TAG_NAME, "img")
                                link_data["favicon"] = {
                                    "url": favicon.get_attribute("src"),
                                    "title": favicon.get_attribute("title"),
                                    "alt": favicon.get_attribute("alt")
                                }

                                # Get the link title and URL
                                link_span = p_element.find_element(By.CSS_SELECTOR, "span[title]")
                                link_element = link_span.find_element(By.CLASS_NAME, "link-title")
                                link_data.update({
                                    "title": link_span.get_attribute("title"),
                                    "url": link_element.get_attribute("href"),
                                    "text": link_element.text
                                })

                                # Try to get summary if it exists
                                try:
                                    summary = link_span.find_element(By.CLASS_NAME, "link-summary")
                                    link_data["summary"] = summary.text
                                except NoSuchElementException:
                                    link_data["summary"] = ""

                            except NoSuchElementException:
                                continue

                            remote_links_data.append(link_data)

                        except (NoSuchElementException, StaleElementReferenceException):
                            continue

                except NoSuchElementException:
                    pass

                return remote_links_data

            # Scrape "links to" section
            linking_data["links_to"] = scrape_remote_links("links to")

            # Scrape "mentioned in" section
            linking_data["mentioned_in"] = scrape_remote_links("mentioned in")

        except NoSuchElementException:
            pass

    except (TimeoutException, StaleElementReferenceException) as e:
        print(f"Error scraping linking module: {str(e)}")
        return None

    return linking_data

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

    # Add linking module data only if it exists
    linking_module_data = scrape_linking_module(driver)
    if linking_module_data is not None:
        issue_data["linking_module"] = linking_module_data

    # Check and click the Activity button if needed
    try:
        for attempt in range(3):  # Retry up to 3 times
            try:
                activity_button = get_element_with_retry(
                    driver,
                    By.CSS_SELECTOR,
                    'button.aui-button.toggle-title[aria-label="Activity"]'
                )

                activity_module = get_element_with_retry(driver, By.ID, "activitymodule")

                if "collapsed" in activity_module.get_attribute("class"):
                    if click_with_retry(driver, activity_button):
                        time.sleep(1)
                        activity_module = get_element_with_retry(driver, By.ID, "activitymodule")
                        if "collapsed" not in activity_module.get_attribute("class"):
                            break
                    else:
                        print(f"Failed to click Activity button on attempt {attempt + 1}")
                else:
                    break

            except (StaleElementReferenceException, TimeoutException) as e:
                if attempt == 2:
                    print(f"Failed to interact with Activity button after 3 attempts on {url}: {str(e)}")
                    return issue_data
                time.sleep(1)

        try:
            all_tab = get_element_with_retry(driver, By.ID, "all-tabpanel")
            if click_with_retry(driver, all_tab):
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "issue-data-block")))
        except (TimeoutException, StaleElementReferenceException) as e:
            print(f"Timeout waiting for 'All' tab on {url}: {str(e)}")
            return issue_data

        issue_data["mod_content"] = safe_find(driver, By.CLASS_NAME, "mod-content")
        issue_data["issue_panel_wrapper"] = safe_find(driver, By.CLASS_NAME, "issuePanelWrapper")

        issue_data["issue_actions"] = []
        try:
            container = get_element_with_retry(driver, By.ID, "issue_actions_container")
            action_items = container.find_elements(By.CLASS_NAME, "issue-data-block")

            for item in action_items:
                try:
                    action_data = {
                        "type": item.get_attribute("id"),
                        "content": item.text
                    }
                    issue_data["issue_actions"].append(action_data)
                except StaleElementReferenceException:
                    continue
        except (NoSuchElementException, TimeoutException):
            pass

        comments = []
        for _ in range(3):
            try:
                comment_elements = driver.find_elements(By.CSS_SELECTOR, ".activity-comment")
                for comment in comment_elements:
                    try:
                        author = comment.find_element(By.CSS_SELECTOR, ".user-hover").text
                        date = comment.find_element(By.CSS_SELECTOR, ".date").get_attribute("title")
                        content = comment.find_element(By.CSS_SELECTOR, ".action-body").text
                        comments.append({"author": author, "date": date, "content": content})
                    except (NoSuchElementException, StaleElementReferenceException):
                        continue
                break
            except StaleElementReferenceException:
                time.sleep(1)
                continue

        issue_data["comments"] = comments

    except Exception as e:
        print(f"Error while scraping additional data for {url}: {str(e)}")

    return issue_data

def get_project_info(url):
    # Try the /browse/ format first
    match = re.search(r'/browse/(\w+)-(\d+)', url)
    if match:
        project = match.group(1)
        number = int(match.group(2))
        return project, f"{project}-{number}", number

    # Try the /projects/ format as fallback
    match = re.search(r'/projects/(\w+)/issues/(\w+-(\d+))', url)
    if match:
        return match.group(1), match.group(2), int(match.group(3))

    return None, None, None

def scrape_project(start_url):
    print(f"Process {os.getpid()} starting to scrape {start_url}")
    driver = None
    try:
        driver = setup_driver()
        project, _, start_number = get_project_info(start_url)
        if not project or not start_number:
            print(f"Invalid URL format: {start_url}")
            return None

        # Create project_data directory if it doesn't exist
        os.makedirs('project_data', exist_ok=True)

        project_data = []
        current_number = start_number

        while current_number > 0:
            url = f"https://issues.apache.org/jira/browse/{project}-{current_number}"
            print(f"Process {os.getpid()} scraping: {url}")

            for attempt in range(3):
                try:
                    issue_data = scrape_issue(driver, url)
                    if issue_data:
                        project_data.append(issue_data)
                        break
                except Exception as e:
                    if attempt == 2:
                        print(f"Failed to scrape issue {project}-{current_number} after 3 attempts: {str(e)}")
                    else:
                        print(f"Retry {attempt + 1}/3 for {url}")
                        time.sleep(2)

            current_number -= 1
            time.sleep(1)

        # Save project data to a JSON file in the project_data directory
        filename = os.path.join('project_data', f"{project}_issues_data.json")
        with open(filename, 'w') as f:
            json.dump(project_data, f, indent=4)

        print(f"Process {os.getpid()} completed scraping project {project}")
        return project

    except Exception as e:
        print(f"Process {os.getpid()} encountered an error: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def main():
    try:
        # Create project_data directory if it doesn't exist
        os.makedirs('project_data', exist_ok=True)

        # Read URLs from file
        with open('sorted_jira_urls.txt', 'r') as file:
            start_urls = [line.strip() for line in file if line.strip()]

        if not start_urls:
            print("No URLs found in jira_urls.txt")
            return

        # Get the number of CPU cores
        num_cores = multiprocessing.cpu_count()
        print(f"Found {num_cores} CPU cores")

        # Use the minimum of number of URLs and CPU cores
        num_processes = min(len(start_urls), num_cores)
        print(f"Using {num_processes} processes")

        # Create a pool of workers
        with Pool(processes=num_processes) as pool:
            # Map the URLs to the pool of workers
            completed_projects = pool.map(scrape_project, start_urls)

        # Print summary
        print("\nScraping Summary:")
        for project in completed_projects:
            if project:
                print(f"Successfully scraped project: {project}")
                print(f"Data saved to: project_data/{project}_issues_data.json")
            else:
                print("Failed to scrape a project")

    except Exception as e:
        print(f"An error occurred in main: {e}")

    print("\nData collection complete.")
    print("All JSON files have been saved in the project_data directory.")

if __name__ == "__main__":
    multiprocessing.freeze_support()  # For Windows compatibility
    main()