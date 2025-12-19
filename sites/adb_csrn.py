import re
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import hashlib

SOURCE = "ADB_CSRN"

URL = "https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE"

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
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session

def _make_stable_id(title: str, deadline: str, link: str) -> str:
    """
    Deterministic stable ID for ADB_CSRN notices
    """
    key = f"{title}|{deadline}|{link}".lower()
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"ADB_CSRN-{digest}"

def fetch_jobs():
    """
    Returns:
        List[Dict[str, str]] with keys:
        - id
        - title
        - deadline
        - link
    """

    session = _get_session()
    response = session.get(URL, timeout=(10, 30))
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    table = soup.select_one("span#atResults table.x1o")
    if not table:
        return results

    rows = table.find_all("tr", recursive=False)

    for row in rows:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 7:
            continue

        # --- Title + link ---
        project_a = cells[0].find("a")
        title = project_a.get_text(strip=True) if project_a else ""
        link = project_a["href"] if project_a and project_a.has_attr("href") else ""

        # --- Deadline ---
        deadline = cells[5].get_text(strip=True)

        # --- CSRN ID (unique identifier) ---
        stable_id = _make_stable_id(title.strip(), deadline.strip(), link.strip())


        # Normalize link (ADB sometimes gives relative URLs)
        if link and link.startswith("/"):
            link = "https://selfservice.adb.org" + link

        results.append({
            "source":SOURCE,
            "id": stable_id,
            "title": title.strip(),
            "deadline": deadline.strip(),
            "link": link.strip(),
        })

    return results

if __name__ == "__main__":
    print(fetch_jobs()[:5])