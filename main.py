import asyncio
import json
import inspect
from pathlib import Path
import re
import unicodedata
import datetime

from email_sender import send_job_email

# ---- import all site modules ----
from sites import undp, afdb, adb_rss, worldbank, adb_csrn,spc, sprep
from llm import classify

# ================== CONFIG ==================
MAX_EMAILS_PER_RUN = 10000          # HARD GLOBAL CAP
MAX_NEW_JOBS_PER_SITE = 1000       # AUTO-STOP THRESHOLD

CACHE_FILE = Path("last_seen.json")
HISTORY_FILE = Path("job_history.json")

SITES = [
    undp,
    afdb,
    adb_rss,
    worldbank,
    adb_csrn,
    spc,
    sprep
]

# ================== CACHE ==================

def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))

# ================== HISTORY ==================

def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return []

def save_history(history):
    # User requested to keep all history in the JSON file indefinitely
    HISTORY_FILE.write_text(json.dumps(history, indent=2))

# ================== UTILS ==================

def normalize(text: str) -> str:
    # convert accented letters to ASCII (é -> e), then remove non-alnum
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

def title_matches(title: str) -> bool:
    t = normalize(title)
    # For single-word keywords, require exact token match; for multi-word, allow substring
    answer=classify(t)
    print(f"LLM response for {t}", answer)
    if answer=="TRUE":
      return True
    elif answer=="FALSE":
      return False
    else:
      raise Exception("LLM not return required output")

async def run_fetch(site):
    """
    Runs fetch_jobs() whether sync or async
    """
    if inspect.iscoroutinefunction(site.fetch_jobs):
        return await site.fetch_jobs()
    else:
        return site.fetch_jobs()

# ================== MAIN ==================

async def main():
    cache = load_cache()
    updated_cache = dict(cache)
    history = load_history()
    run_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    emails_sent = 0   # GLOBAL COUNTER

    for site in SITES:
        source = site.SOURCE
        print(f"\n🔍 Checking {source}")

        if site == spc:
            last_seen_id = set(cache.get(source, []))
        else:
            last_seen_id = cache.get(source)

        try:
            jobs = await run_fetch(site)
        except Exception as e:
            print(f"❌ {source} failed: {e}")
            save_cache(updated_cache)
            continue

        if not jobs:
            print(f"⚠️ No jobs fetched for {source}")
            save_cache(updated_cache)
            continue

        # ---------- COLLECT NEW JOBS ----------
        new_jobs = []
        
        if site == spc:
            for job in jobs:
                if job["id"] not in last_seen_id:
                    new_jobs.append(job)
        else:
            for job in jobs:
                if job["id"] == last_seen_id:
                    break
                new_jobs.append(job)

        print(f"🆕 {len(new_jobs)} new jobs for {source}")

        # ---------- AUTO-STOP ON SUSPICIOUS SPIKE ----------
        if len(new_jobs) > MAX_NEW_JOBS_PER_SITE:
            print(
                f"🚨 AUTO-STOP: {len(new_jobs)} new jobs for {source}. "
                "Possible cache reset or site change. No emails sent."
            )
            if site!=spc:
                updated_cache[source] = new_jobs[0]["id"]
            else:
                prev_ids = set(cache.get(source, []))
                current_ids = {job["id"] for job in jobs}
                updated_cache[source] = list(prev_ids | current_ids)
            save_cache(updated_cache)
            continue

        # ---------- SEND EMAILS (WITH HARD CAP) ----------
        for job in new_jobs:
            if emails_sent >= MAX_EMAILS_PER_RUN:
                raise RuntimeError(
                    f"🛑 ABORTING RUN: Email limit exceeded "
                    f"({emails_sent} >= {MAX_EMAILS_PER_RUN})"
                )

            is_relevant = title_matches(job["title"])
            
            # Record history
            history.append({
                "id": job["id"],
                "title": job["title"],
                "link": job["link"],
                "source": source,
                "relevant": is_relevant,
                "date": run_date
            })

            if is_relevant:
                print(f"📧 Sending email: {job['id']}")
                send_job_email(
                    title=job["title"],
                    link=job["link"],
                    ref_no=job["id"],
                    country=job.get("country"),
                    process=job.get("process"),
                    deadline=job.get("deadline"),
                )
                emails_sent += 1

        # ---------- UPDATE CACHE ----------
        if new_jobs:
            if site!=spc:
                updated_cache[source] = new_jobs[0]["id"]
            else:
                prev_ids = set(cache.get(source, []))
                current_ids = {job["id"] for job in jobs}
                updated_cache[source] = list(prev_ids | current_ids)

        save_cache(updated_cache)

    print(f"\n✅ Done. Emails sent: {emails_sent}")
    save_history(history)
    generate_html(history)

# ================== HTML GENERATION ==================

def generate_html(history):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tender Alerts History</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
        
        :root {{
            --bg-color: #121212;
            --text-color: #e0e0e0;
            --accent-color: #bb86fc;
            --border-color: #333;
            --row-hover: #1e1e1e;
            --true-color: #4caf50;
            --false-color: #f44336;
        }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 40px 20px;
        }}
        h1 {{
            text-align: center;
            color: var(--accent-color);
            margin-bottom: 30px;
            font-weight: 600;
        }}
        .controls {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        select, input {{
            padding: 12px 15px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background-color: #1e1e1e;
            color: white;
            font-size: 14px;
            outline: none;
            transition: border-color 0.3s;
        }}
        select:focus, input:focus {{
            border-color: var(--accent-color);
        }}
        table {{
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
            border-collapse: collapse;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4);
            background-color: #1e1e1e;
            border-radius: 12px;
            overflow: hidden;
        }}
        th, td {{
            padding: 16px 20px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background-color: #2c2c2c;
            color: var(--accent-color);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 1px;
        }}
        tr:hover td {{
            background-color: var(--row-hover);
        }}
        tr {{
            transition: background-color 0.2s ease;
        }}
        a {{
            color: #64b5f6;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s;
        }}
        a:hover {{
            color: #90caf9;
            text-decoration: underline;
        }}
        .badge {{
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }}
        .badge.true {{
            background-color: rgba(76, 175, 80, 0.15);
            color: var(--true-color);
            border: 1px solid rgba(76, 175, 80, 0.3);
        }}
        .badge.false {{
            background-color: rgba(244, 67, 54, 0.15);
            color: var(--false-color);
            border: 1px solid rgba(244, 67, 54, 0.3);
        }}
        .source {{
            color: #aaa;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <h1>Tender Alerts History</h1>
    <div class="controls">
        <input type="text" id="searchInput" placeholder="Search by ID or Title..." onkeyup="filterTable()">
        <select id="relevanceFilter" onchange="filterTable()">
            <option value="ALL">All Jobs</option>
            <option value="TRUE">Relevant (TRUE)</option>
            <option value="FALSE">Not Relevant (FALSE)</option>
        </select>
    </div>
    <table id="jobsTable">
        <thead>
            <tr>
                <th>Date</th>
                <th>Source</th>
                <th>ID</th>
                <th>Title</th>
                <th>Relevance</th>
                <th>Link</th>
            </tr>
        </thead>
        <tbody>
"""
    # Sort history by date descending, relying on Python's stable sort to keep 
    # the original processing order within the same run.
    sorted_history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)
    
    # Display maximum 10,000 entries on the site so the browser doesn't crash
    display_history = sorted_history[:10000]

    for job in display_history:
        rel_str = "TRUE" if job["relevant"] else "FALSE"
        rel_class = "true" if job["relevant"] else "false"
        title = str(job.get('title', '')).replace('<', '&lt;').replace('>', '&gt;')
        date_str = job.get('date', 'N/A')
        html += f"""
            <tr>
                <td><span class="source">{date_str}</span></td>
                <td><span class="source">{job.get('source', 'Unknown')}</span></td>
                <td>{job.get('id', '')}</td>
                <td>{title}</td>
                <td><span class="badge {rel_class}">{rel_str}</span></td>
                <td><a href="{job.get('link', '#')}" target="_blank">View</a></td>
            </tr>"""

    html += """
        </tbody>
    </table>
    <script>
        function filterTable() {
            const searchInput = document.getElementById('searchInput').value.toLowerCase();
            const relevanceFilter = document.getElementById('relevanceFilter').value;
            const table = document.getElementById('jobsTable');
            const tr = table.getElementsByTagName('tr');

            for (let i = 1; i < tr.length; i++) {
                const tds = tr[i].getElementsByTagName('td');
                if (tds.length > 0) {
                    const dateText = tds[0].textContent || tds[0].innerText;
                    const idText = tds[2].textContent || tds[2].innerText;
                    const titleText = tds[3].textContent || tds[3].innerText;
                    const relText = tds[4].textContent || tds[4].innerText;
                    
                    const matchesSearch = titleText.toLowerCase().indexOf(searchInput) > -1 || idText.toLowerCase().indexOf(searchInput) > -1 || dateText.toLowerCase().indexOf(searchInput) > -1;
                    const matchesFilter = relevanceFilter === 'ALL' || relText.trim() === relevanceFilter;

                    if (matchesSearch && matchesFilter) {
                        tr[i].style.display = '';
                    } else {
                        tr[i].style.display = 'none';
                    }
                }
            }
        }
    </script>
</body>
</html>"""
    Path("index.html").write_text(html, encoding="utf-8")

# ================== ENTRY ==================

if __name__ == "__main__":
    asyncio.run(main())
