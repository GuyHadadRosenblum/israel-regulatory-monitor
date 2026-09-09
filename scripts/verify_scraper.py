"""Read one live page using the actual collector selectors; no full crawl."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.legislation_scraper import setup_driver, get_inner_page_data
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver=setup_driver()
driver.set_page_load_timeout(40)
try:
    driver.get('https://www.tazkirim.gov.il/s/?language=iw')
    WebDriverWait(driver,30).until(EC.presence_of_element_located((By.CSS_SELECTOR,'div.cardBody')))
    cards=driver.find_elements(By.CSS_SELECTOR,'div.cardBody')
    print('LIVE_CARDS',len(cards),flush=True)
    card=cards[0]
    link=card.find_element(By.CSS_SELECTOR,'h2.header-title a').get_attribute('href')
    print('DATE_SELECTOR',bool(card.find_element(By.CSS_SELECTOR,'span.header-date:nth-of-type(3)').text),flush=True)
    print('OFFICE_SELECTOR',bool(card.find_element(By.CSS_SELECTOR,'span.header-account a').text),flush=True)
    result=get_inner_page_data(driver,link)
    print('DETAIL_FIELDS',len(result),flush=True)
finally:
    driver.quit()
