import re
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import hashlib
from playwright.sync_api import sync_playwright

SOURCE = "SPREP"

URL = "https://www.sprep.org/tenders"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}


def _get_session():
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def _normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"[^\w\s]", "", title)
    return title.strip()


def _make_stable_id(title: str) -> str:
    norm_title = _normalize_title(title)
    digest = hashlib.sha256(norm_title.encode("utf-8")).hexdigest()[:16]
    return f"{SOURCE}-{digest}"


def fetch_jobs():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("https://www.sprep.org/tenders", timeout=30000)
        page.wait_for_timeout(3000)

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    results = []

    table = soup.select_one("table.ct-table")
    if not table:
        return results

    rows = table.select("tbody tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 1:
            continue

        tender_col = cols[0]

        # --- Title + link ---
        a_tag = tender_col.find("a", href=True)
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        link = a_tag["href"]

        if link.startswith("/"):
            link = "https://www.sprep.org" + link

        # --- Deadline ---
        text = tender_col.get_text(" ", strip=True)

        deadline = ""
        match = re.search(r"Due Date:\s*(.*)", text)
        if match:
            deadline = match.group(1)

        # --- Stable ID ---
        stable_id = _make_stable_id(title)

        results.append({
            "source": SOURCE,
            "id": stable_id,
            "title": title,
            "deadline": deadline,
            "link": link,
        })

    return results


if __name__ == "__main__":
    jobs = fetch_jobs()
    print(len(jobs))
    print(jobs[:5])