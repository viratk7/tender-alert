from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

SOURCE = "WORLD_BANK"

URL = "https://projects.worldbank.org/en/projects-operations/procurement?srce=both"
BASE = "https://projects.worldbank.org"

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

        # Block heavy resources
        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "font", "media"}
            else route.continue_()
        )

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
        if len(cols) < 2:
            continue

        # --- title + link ---
        a = cols[0].find("a")
        if not a or not a.get("href"):
            continue

        title = a.get_text(strip=True)
        link = urljoin(BASE, a["href"])

        # --- unique ID (World Bank project code) ---
        project_code = urlparse(link).path.rstrip("/").split("/")[-1]
        unique_id = f"WORLD_BANK-{project_code}"

        # --- deadline (best available column) ---
        deadline = ""
        if len(cols) >= 6:
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