import asyncio
import json
import inspect
from pathlib import Path
import re

from email_sender import send_job_email

# ---- import all site modules ----
from sites import undp, afdb, adb_rss, worldbank, adb_csrn

# ================== CONFIG ==================

KEYWORDS = [
    # ================= English =================
    "climate",
    "environment",
    "energy",
    "sustainable",
    "renewable",
    "sustainability",
    "green",

    # UNFCCC / reporting
    "ndc",
    "ndc 3.0",
    "nationally determined contribution",
    "btr",
    "biennial transparency report",
    "national communication",
    "reporting",
    "transparency",
    "mrv",
    "stocktake",
    "global stocktake",

    # Climate action
    "mitigation",
    "adaptation",
    "emission",
    "ghg",
    "climate finance",
    "green finance",
    "taxonomy",
    "electricity",

    # ================= French =================
    "climat",
    "environnement",
    "énergie",
    "durable",
    "renouvelable",
    "durabilité",
    "vert",

    # UNFCCC / reporting (FR)
    "cdn",  # Contribution déterminée au niveau national
    "contribution déterminée au niveau national",
    "rapport biennal de transparence",
    "communication nationale",
    "rapportage",
    "transparence",
    "mrv",  # same acronym in French
    "bilan mondial",

    # Climate action (FR)
    "atténuation",
    "adaptation",
    "émission",
    "ges",  # gaz à effet de serre
    "finance climatique",
    "finance verte",
    "taxonomie",
    "électricité",
]


MAX_EMAILS_PER_RUN = 10          # HARD GLOBAL CAP
MAX_NEW_JOBS_PER_SITE = 15       # AUTO-STOP THRESHOLD

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

def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower())

def title_matches(title: str) -> bool:
    t = normalize(title)
    return any(normalize(k) in t for k in KEYWORDS)

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

        # ---------- FIRST RUN SAFETY ----------
        if last_seen_id is None:
            print(f"🛑 FIRST RUN for {source} — baseline set, NO emails sent")
            updated_cache[source] = jobs[0]["id"]
            save_cache(updated_cache)
            continue

        # ---------- COLLECT NEW JOBS ----------
        new_jobs = []
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
            updated_cache[source] = new_jobs[0]["id"]
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
            updated_cache[source] = new_jobs[0]["id"]

        save_cache(updated_cache)

    print(f"\n✅ Done. Emails sent: {emails_sent}")

# ================== ENTRY ==================

if __name__ == "__main__":
    asyncio.run(main())
