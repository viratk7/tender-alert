import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import datetime

SOURCE = "SPC"
URL = "https://www.spc.int/procurement"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _get_session():
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def compare_dates(date1, date2):
    return date1 == date2

def fetch_jobs():
    session = _get_session()
    resp = session.get(URL, timeout=(10, 30))
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    rows = soup.select("table tbody tr")
    jobs = []
    today_date = datetime.date.today().isoformat()

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 2:
            continue
            
        # Dates
        times = cols[1].find_all("time")
        
        date_posted = ""
        deadline = ""
        
        if len(times) >= 1:
            date_posted = times[0]["datetime"].split("T")[0]
        
        if len(times) >= 2:
            deadline = times[1]["datetime"].split("T")[0]
        
        if not compare_dates(date_posted, today_date):
            continue

        # Ref No
        ref_no = cols[0].get_text(strip=True)
        if not ref_no:
            continue

        # Title + link + dates are in column 1
        title_link = cols[1].find("a")
        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        link = "https://www.spc.int" + title_link["href"]

        

        jobs.append({
            "source": SOURCE,
            "id": ref_no,
            "title": title,
            "date_posted": date_posted,
            "deadline": deadline,
            "link": link,
        })

    return jobs


if __name__ == "__main__":
    jobs = fetch_jobs()
    with open("jobs.txt", "w", encoding="utf-8") as f:
        f.write(str(jobs))