import asyncio
import json
import inspect
from pathlib import Path
import re
import unicodedata

from email_sender import send_job_email

# ---- import all site modules ----
from sites import undp, afdb, adb_rss, worldbank, adb_csrn,spc, sprep
from llm import classify

# ================== CONFIG ==================
MAX_EMAILS_PER_RUN = 10          # HARD GLOBAL CAP
MAX_NEW_JOBS_PER_SITE = 15       # AUTO-STOP THRESHOLD

CACHE_FILE = Path("last_seen.json")

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

            if title_matches(job["title"]):
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

# ================== ENTRY ==================

if __name__ == "__main__":
    asyncio.run(main())
