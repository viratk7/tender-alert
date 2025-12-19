import asyncio
import json
import inspect
from pathlib import Path

from email_sender import send_job_email

# ---- import all site modules ----
from sites import undp, afdb, adb_rss, worldbank, adb_csrn

# ---- CONFIG ----
KEYWORDS = [
    "climate",
    "environment",
    "energy",
    "green",
    "sustainable"
]

CACHE_FILE = Path("last_seen.json")

SITES = [
    undp,
    afdb,
    adb_rss,
    worldbank,
    adb_csrn,
]


# ================== CACHE ==================

def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


# ================== UTILS ==================

def title_matches(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in KEYWORDS)


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

    for site in SITES:
        source = site.SOURCE
        print(f"\n🔍 Checking {source}")

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

        new_jobs = []

        for job in jobs:
            if last_seen_id and job["id"] == last_seen_id:
                break
            new_jobs.append(job)

        print(f"🆕 {len(new_jobs)} new jobs for {source}")

        for job in new_jobs:
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

        if new_jobs:
            updated_cache[source] = new_jobs[0]["id"]

        # ✅ persist after EACH site
        save_cache(updated_cache)

    print("\n✅ Done.")



if __name__ == "__main__":
    asyncio.run(main())
