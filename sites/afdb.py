from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

SOURCE = "AFDB"

URL = "https://www.afdb.org/en/about-us/careers/current-vacancies/consultants"
BASE = "https://www.afdb.org"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


async def _fetch_html() -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_selector("table", timeout=30000)

        html = await page.content()
        await browser.close()
        return html


async def fetch_jobs():
    """
    Returns:
        List[Dict[str, str]] with keys:
        - source
        - id
        - title
        - deadline
        - link
    """

    html = await _fetch_html()
    soup = BeautifulSoup(html, "html.parser")

    jobs = []
    table = soup.select_one("table")
    if not table:
        return jobs

    rows = table.select("tbody tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        a = cols[0].find("a")
        if not a or not a.get("href"):
            continue

        title = a.get_text(strip=True)
        link = urljoin(BASE, a["href"])

        # unique vacancy slug
        slug = urlparse(link).path.rstrip("/").split("/")[-1]
        unique_id = f"AFDB-{slug}"

        deadline = cols[-1].get_text(strip=True)

        jobs.append({
            "source": SOURCE,
            "id": unique_id,
            "title": title,
            "deadline": deadline,
            "link": link,
        })

    return jobs

if __name__ == "__main__":
    import asyncio

    async def _test():
        jobs = await fetch_jobs()
        print(len(jobs))
        print(jobs[:3])

    asyncio.run(_test())

