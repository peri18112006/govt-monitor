import hashlib
import logging
import os
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("govt_monitor.scraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# "edge" for local Windows runs (matches your existing Selenium setup),
# "chrome" for GitHub Actions / Linux runners (Chrome is preinstalled there, Edge isn't).
SELENIUM_BROWSER = os.getenv("SELENIUM_BROWSER", "edge").lower()


def _get_html_requests(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _get_html_selenium(url: str, wait_seconds: int = 10) -> str:
    """
    Renders the page with a headless browser and returns the final HTML.
    Needed for JS-heavy / SPA sites where content loads via AJAX after page load.

    Browser is chosen via SELENIUM_BROWSER env var:
    - "edge"   -> local Windows runs (avoids corporate ChromeDriver policy blocks)
    - "chrome" -> GitHub Actions / Linux runners (Chrome/Chromium is preinstalled)

    Uses Selenium 4's built-in Selenium Manager, so no manual driver download
    is needed on either platform - it auto-detects your installed browser
    version and fetches the matching driver.
    """
    from selenium import webdriver

    if SELENIUM_BROWSER == "chrome":
        from selenium.webdriver.chrome.options import Options as BrowserOptions
        driver_cls = webdriver.Chrome
    else:
        from selenium.webdriver.edge.options import Options as BrowserOptions
        driver_cls = webdriver.Edge

    options = BrowserOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")

    driver = driver_cls(options=options)
    try:
        driver.get(url)
        time.sleep(wait_seconds)  # let JS/AJAX finish loading
        return driver.page_source
    finally:
        driver.quit()


def get_page_html(url: str, renderer: str = "requests", timeout: int = 20) -> str:
    if renderer == "selenium":
        return _get_html_selenium(url)
    return _get_html_requests(url, timeout)


def extract_items(html: str, selector: str, base_url: str, max_items: int = 40):
    """
    Extracts a list of {title, url} news/announcement items from the given
    section of the page (found via `selector`). Looks for <a> links, since
    government notification/circular/announcement lists are almost always
    rendered as a list of links.

    Returns a list of dicts: [{"title": "...", "url": "https://..."}]
    Deduplicated by URL, in the order they appear on the page (usually newest first).
    """
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(selector) or soup.body or soup

    for tag in node.find_all(["script", "style", "noscript"]):
        tag.decompose()

    items = []
    seen_urls = set()

    for a in node.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = a["href"].strip()

        if not title or len(title) < 8:
            continue
        if href.startswith("#") or href.lower().startswith("javascript:"):
            continue

        full_url = urljoin(base_url, href)
        if full_url in seen_urls:
            continue

        seen_urls.add(full_url)
        items.append({"title": title, "url": full_url})

        if len(items) >= max_items:
            break

    return items


def extract_plain_text(html: str, selector: str) -> str:
    """
    Fallback: extracts plain visible text of a section (no links needed).
    Used for sites where the update isn't a clean link-list (e.g. a ticker/banner).
    """
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(selector) or soup.body or soup
    for tag in node.find_all(["script", "style", "noscript"]):
        tag.decompose()
    return node.get_text(separator="\n", strip=True)


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_site_for_change(site: dict, previous_titles: set | None):
    """
    Fetches the site, extracts news items (title + link), and figures out
    which ones are NEW compared to the previous check.

    Returns: (new_items: list[dict], is_first_check: bool, all_items: list[dict], plain_text: str)
    """
    url = site["url"]
    renderer = site.get("renderer", "requests")
    selector = site.get("selector", "body")

    html = get_page_html(url, renderer)
    items = extract_items(html, selector, url)
    plain_text = extract_plain_text(html, selector)

    is_first_check = previous_titles is None

    if is_first_check or not items:
        # First check (baseline) or no clean link-list found on this page
        new_items = []
    else:
        new_items = [i for i in items if i["title"] not in previous_titles]

    return new_items, is_first_check, items, plain_text
