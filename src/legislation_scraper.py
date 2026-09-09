import os
import time
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'legislation_website_data.csv')


def setup_driver():
    from src.browser_factory import chrome
    return chrome()


def get_inner_page_data(driver, url):
    """Extracts metadata using the robust innerText method proven in debug."""
    data = {
        "url": url,
        "internal_title": "N/A",
        "legislation_type": "Other",  # Default value
        "main_file_url": "N/A",
        "has_standard_ria": "No",
        "standard_ria_url": "N/A",
        "has_ria_exemption": "No",
        "ria_exemption_url": "N/A",
        "description": "N/A",
        "subjects": "N/A"
    }

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "pageMain")))

        # Give Salesforce time to inject the Hebrew text
        time.sleep(1)

        # 1. Internal Title
        try:
            data["internal_title"] = driver.find_element(By.CSS_SELECTOR, "div.title").get_attribute(
                "innerText").strip()
        except:
            pass

        # 2. Main File Link and Legislation Type Extraction (Looping Logic)
        try:
            # Explicitly wait for the class to appear
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "law-url-span")))
            # Extra buffer for Salesforce JS injection as proven in debug
            time.sleep(2)

            try:
                # 1. Force the driver to look only inside the desktop wrapper, ignoring the buggy mobile layout
                additional_section = driver.find_element(By.CSS_SELECTOR, "div.additional.desktopDisplay")

                # 2. Extract links strictly contained within this desktop section
                all_links = additional_section.find_elements(By.CLASS_NAME, "law-url-span")
            except:
                all_links = []

            for link in all_links:
                # Get the actual HTML code and the visible text from the browser
                element_html = link.get_attribute("outerHTML")
                link_text = link.get_attribute("innerText").strip()
                link_url = link.get_attribute("href")

                if not link_text:
                    continue

                # Print the exact HTML snippet so you can verify the source
                print(f"\n      [DEBUG] Inspecting Element: {element_html}")
                print(f"      [DEBUG] Detected Text: '{link_text}'")

                if "תזכיר החוק" in link_text:
                    print(f"      [MATCH] Keyword 'תזכיר החוק' found! Tagging as Primary Legislation.")
                    data["legislation_type"] = "Primary Legislation"
                    data["main_file_url"] = link_url
                    break
                elif "חקיקת משנה" in link_text:
                    print(f"      [MATCH] Keyword 'חקיקת משנה' found! Tagging as Secondary Legislation.")
                    data["legislation_type"] = "Secondary Legislation"
                    data["main_file_url"] = link_url
                elif "מבחן התמיכה" in link_text:
                    print(f"      [MATCH] Keyword 'מבחן התמיכה' found! Tagging as Support Test.")
                    data["legislation_type"] = "Support Test"
                    data["main_file_url"] = link_url
                elif "טיוטת המסמך" in link_text:
                    print(f"      [MATCH] Keyword 'טיוטת המסמך' found! Tagging with empty legislation type.")
                    data["legislation_type"] = ""
                    data["main_file_url"] = link_url
                else:
                    # This single else handles everything that doesn't match the keywords above
                    print(f"      [NO MATCH] This element does not contain your keywords.")
        except Exception as e:
            print(f"      [!] Error identifying legislation type: {e}")

        # 3. RIA Logic (Targeted and Categorized)
        try:
            # Find the RIA section specifically
            ria_xpath = "//div[contains(@class, 'additional-div')][.//h1[contains(text(), 'RIA:')]]"
            ria_sections = driver.find_elements(By.XPATH, ria_xpath)

            if ria_sections:
                links = ria_sections[0].find_elements(By.TAG_NAME, "a")
                for link in links:
                    text = link.get_attribute("innerText").strip()
                    url_val = link.get_attribute("href")

                    if not text: continue

                    if "פטור" in text:
                        data["has_ria_exemption"] = "Yes"
                        data["ria_exemption_url"] = url_val
                    else:
                        data["has_standard_ria"] = "Yes"
                        data["standard_ria_url"] = url_val
        except:
            pass

        # 4. Description
        try:
            desc = driver.find_element(By.CSS_SELECTOR, "lightning-formatted-rich-text")
            data["description"] = desc.get_attribute("innerText").replace('\n', ' ').strip()
        except:
            pass

        # 5. Subjects
        try:
            subj = driver.find_elements(By.CLASS_NAME, "classifications")
            if subj:
                data["subjects"] = subj[0].get_attribute("innerText").strip()
        except:
            pass

    except Exception as e:
        raise RuntimeError(f"Could not read publication details: {url}") from e

    return data


def scrape_legislation_portal(target_date_str="01/01/2026"):
    target_date = datetime.strptime(target_date_str, "%d/%m/%Y")
    driver = setup_driver()

    if os.path.exists(OUTPUT_PATH):
        existing_df = pd.read_csv(OUTPUT_PATH)
        existing_urls = set(existing_df['url'].tolist())
    else:
        existing_df = pd.DataFrame()
        existing_urls = set()

    try:
        driver.get("https://www.tazkirim.gov.il/s/?language=iw")
        wait = WebDriverWait(driver, 15)

        new_entries = []
        stop_signal = False
        seen_urls_this_session = set()  # NEW: Track URLs seen in this run

        while not stop_signal:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.cardBody")))
            cards = driver.find_elements(By.CSS_SELECTOR, "div.cardBody")

            for card in cards:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, "h2.header-title a")
                    url = title_elem.get_attribute("href")

                    # Skip if we already processed it during THIS run session
                    if url in seen_urls_this_session:
                        continue

                    # 1. Extract and evaluate the publish date FIRST to enforce the time boundary accurately
                    date_text = card.find_element(By.CSS_SELECTOR, "span.header-date:nth-of-type(3)").text
                    if datetime.strptime(date_text, "%d/%m/%Y") < target_date:
                        print(f"[*] Reached target date {target_date_str}. Stopping browser scrape session.")
                        stop_signal = True
                        break

                    # 2. If it is within the time boundary but already in your CSV, skip it instead of stopping
                    if url in existing_urls:
                        print(f"[*] Cached: '{title_elem.text}' already exists in database. Skipping row.")
                        seen_urls_this_session.add(url)
                        continue

                    # Mark as seen
                    seen_urls_this_session.add(url)

                    office = card.find_element(By.CSS_SELECTOR, "span.header-account a").get_attribute("innerText")
                    new_entries.append(
                        {"title": title_elem.text, "url": url, "office": office, "publish_date": date_text})
                    print(f"[*] Discovered: {title_elem.text}")

                except Exception:
                    continue

            if stop_signal: break

            try:
                btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.LoadMore")))
                driver.execute_script("arguments[0].scrollIntoView();", btn)
                time.sleep(1)
                btn.click()
                time.sleep(1)
            except:
                break

        if new_entries:
            print(f"\n[*] Deep-scraping {len(new_entries)} links...")
            processed = []
            for entry in new_entries:
                print(f"   -> {entry['title']}")
                details = get_inner_page_data(driver, entry['url'])
                entry.update(details)
                processed.append(entry)

            new_df = pd.DataFrame(processed)
            final_df = pd.concat([new_df, existing_df], ignore_index=True).drop_duplicates(subset=['url'])
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            final_df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
            print(f"\n[*] Update finished. {len(processed)} items added.")
        else:
            print("\n[*] No new items found.")

    finally:
        driver.quit()


if __name__ == "__main__":
    scrape_legislation_portal(target_date_str="15/04/2026")
