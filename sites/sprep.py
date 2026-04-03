from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import hashlib
import asyncio
import re

SOURCE = "SPREP"
URL = "https://www.sprep.org/tenders"


def _normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"[^\w\s]", "", title)
    return title.strip()


def _make_stable_id(title: str) -> str:
    norm_title = _normalize_title(title)
    digest = hashlib.sha256(norm_title.encode("utf-8")).hexdigest()[:16]
    return f"{SOURCE}-{digest}"


async def fetch_jobs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(URL, timeout=60000)
        await page.wait_for_timeout(3000)

        html = await page.content()
        await browser.close()

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

        a_tag = tender_col.find("a", href=True)
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        link = a_tag["href"]

        if link.startswith("/"):
            link = "https://www.sprep.org" + link

        text = tender_col.get_text(" ", strip=True)

        deadline = ""
        match = re.search(r"Due Date:\s*(.*)", text)
        if match:
            deadline = match.group(1)

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
    jobs = asyncio.run(fetch_jobs())
    print(len(jobs))
    print(jobs[:5])