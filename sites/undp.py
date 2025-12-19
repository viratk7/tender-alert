import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SOURCE = "UNDP"

URL = "https://procurement-notices.undp.org/index.cfm?cur_lang=en"

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


def _get_field(job, label_text):
    cells = job.select("div.vacanciesTable__cell")
    for cell in cells:
        label = cell.select_one(".vacanciesTable__cell__label")
        value = cell.select_one("span")
        if label and value and label_text.lower() in label.get_text(strip=True).lower():
            return value.get_text(" ", strip=True)
    return None


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
    rows = soup.select("a.vacanciesTableLink")

    jobs = []

    for row in rows:
        ref_no = _get_field(row, "Ref No")
        title = _get_field(row, "Title")
        deadline = _get_field(row, "Deadline")

        if not ref_no or not title:
            continue

        jobs.append({
            "source": SOURCE,
            "id": ref_no.strip(),
            "title": title.strip(),
            "deadline": deadline.strip() if deadline else "",
            "link": "https://procurement-notices.undp.org/" + row["href"],
        })

    return jobs

if __name__=="__main__":
    print(fetch_jobs())