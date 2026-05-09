import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SOURCE = "UNIDO"

def fetch_jobs():
    url = "https://www.unido.org/get-involved/procurement/procurement-opportunities"
    
    html = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # use domcontentloaded instead of networkidle to prevent timeouts
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"Error fetching UNIDO via Playwright: {e}")
        return []

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    
    # The image shows a standard table. We'll find all tables and look for the one with 'Event Number'
    tables = soup.find_all("table")
    
    target_table = None
    for table in tables:
        headers_text = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if "event number" in headers_text or "title" in headers_text:
            target_table = table
            break
            
    if not target_table:
        print("Could not find the target table on UNIDO page.")
        return []
        
    rows = target_table.find_all("tr")
    
    for row in rows[1:]:  # Skip header row
        cols = row.find_all(["td", "th"])
        if len(cols) < 5:
            continue
            
        title = cols[0].get_text(strip=True)
        country = cols[1].get_text(strip=True)
        deadline = cols[2].get_text(strip=True)
        process = cols[3].get_text(strip=True)
        event_number = cols[4].get_text(strip=True)
        
        link = url
        # Try to find a link in the last column (Registration) or first column
        link_tag = cols[-1].find("a")
        if not link_tag:
             link_tag = cols[0].find("a")
             
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            if href.startswith("/"):
                link = "https://www.unido.org" + href
            else:
                link = href
                
        # Fallback ID if event number is empty
        job_id = f"UNIDO-{event_number}" if event_number else f"UNIDO-{hash(title)}"
        
        jobs.append({
            "id": job_id,
            "title": title,
            "link": link,
            "country": country,
            "process": process,
            "deadline": deadline
        })
        
    return jobs

if __name__ == "__main__":
    jobs = fetch_jobs()
    print(f"Found {len(jobs)} jobs.")
    for j in jobs:
        print(j)
