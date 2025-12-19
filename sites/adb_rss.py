import requests
import xml.etree.ElementTree as ET

SOURCE = "ADB_RSS"
URL = "https://www.adb.org/rss/tenders/all/all/all/consulting/all/all"


def fetch_jobs():
    """
    ADB RSS feed (Cloudflare-safe)

    Returns:
        List[Dict[str, str]]
    """
    jobs = []

    r = requests.get(URL, timeout=20)
    r.raise_for_status()

    root = ET.fromstring(r.text)

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        if not title or not link:
            continue

        # Drupal node ID is stable & unique
        node_id = link.rstrip("/").split("/")[-1]
        unique_id = f"ADB-{node_id}"

        jobs.append({
            "source": SOURCE,
            "id": unique_id,
            "title": title,
            "deadline": "",   # RSS does not include deadline
            "link": link,
        })

    return jobs

if __name__=="__main__":
    print(fetch_jobs())