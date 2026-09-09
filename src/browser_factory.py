"""Headless Chrome setup shared by collector and document downloader."""
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

def chrome(download_dir=None):
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-dev-shm-usage')
    if os.environ.get('CHROME_NO_SANDBOX') == 'true':
        options.add_argument('--no-sandbox')
    if os.environ.get('CHROME_BIN'):
        options.binary_location = os.environ['CHROME_BIN']
    if download_dir:
        options.add_experimental_option('prefs', {'download.default_directory': os.path.abspath(download_dir), 'download.prompt_for_download': False, 'plugins.always_open_pdf_externally': True})
    path = os.environ.get('CHROMEDRIVER')
    return webdriver.Chrome(service=Service(path) if path else Service(), options=options)
