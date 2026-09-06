import asyncio
from playwright.async_api import async_playwright
from log_config import log
import os
import json
import html
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SIT_USERNAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "jobs.json"
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 3600))


def load_saved_jobs() -> dict:
    #read for json data file
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load saved jobs from {DATA_FILE}: {e}")
    return {}

#save jobs from API call
def save_jobs(jobs: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

#my headless login to retrive data from api
async def login(page, SIT_USERNAME, PASSWORD):
    log.info("navigating to readytalent")
    await page.goto("https://readytalent2.singaporetech.edu.sg/")

    log.info("clicking Staff/Student/Alumni login")
    await page.evaluate("checkAuth()")

    log.info("waiting for ADFS page")
    await page.wait_for_load_state("networkidle", timeout=60000)

    log.info("filling credentials")
    await page.fill("#userNameInput", SIT_USERNAME)
    await page.fill("#passwordInput", PASSWORD)

    log.info("submitting login")
    await page.click("#submitButton")

    await page.wait_for_load_state("networkidle", timeout=60000)
    log.info("login complete")

    await page.wait_for_timeout(5000)


# fetches part time jobs for student only
async def fetch_jobs(page, studentId, requestname="LoadPartTimeJobDetailsStudentDashboard"):
    url = f"https://mvw9e7kvt9.execute-api.ap-southeast-1.amazonaws.com/Prod?requestname={requestname}&studentId={studentId}&accessLevelCondition=&loginaccessType=Student"

    # log.info(f"requesting: {url}")
    response_json = await page.evaluate(f"""
        async () => {{
            const res = await fetch("{url}", {{
                method: "POST",
                headers: {{"Apitoken": sessionStorage.getItem('apitoken')}},
            }});
            return await res.json();
        }}
    """)
    return response_json


# parse jobs to get SIT student work scheme
def parse_jobs(response_json):
    return {
        job['sit_jobpostingid']: {
            'job_title': job['sit_name'],
            'company_name': job['acc.name'],
            'number_of_vacancies': job['sit_numberofvacancies'],
        }
        for job in response_json
        if "SIT Student Work Scheme" in job.get('_sit_employmenttype_value@OData.Community.Display.V1.FormattedValue', '')
    }

#handles job listing call 
async def get_job_lists(initial=False):
    log.info("Starting job list retrieval")


    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await login(page, SIT_USERNAME , PASSWORD)
            studentId = await page.evaluate("sessionStorage.getItem('StudentId')")

            response_json = await fetch_jobs(page, studentId)

            for job in response_json:
                emp_type = job.get('_sit_employmenttype_value@OData.Community.Display.V1.FormattedValue', '')

            job_list = parse_jobs(response_json)

            if initial:
                while len(job_list) == 0:
                    log.info("Initial API call returned no jobs, retrying...")
                    response_json = await fetch_jobs(page, studentId)
                    job_list = parse_jobs(response_json)
                # log.info(f"Initial job list retrieval completed with {len(job_list)} jobs")
            else:
                if len(job_list) == 0:
                    log.info("Subsequent API call returned no jobs, keeping the current job list")
                    return {}

            log.info(job_list)
            return job_list

        except Exception as e:
            log.error(f"Error in get_job_list: {e}")
            return {}

        finally:
            await browser.close()

def _send_telegram_sync(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


async def send_telegram_message(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured in .env. Skipping Telegram message.")
        return
    try:
        await asyncio.to_thread(_send_telegram_sync, token, chat_id, text)
        log.info("Telegram notification sent successfully.")
    except Exception as e:
        log.error(f"Failed to send Telegram message: {e}")
        log.error(f"Exact Reason: {e.read().decode('utf-8')}") # This reads the Telegram JSON error description



# fires when new job is detected
async def handle_new_jobs(new_jobs: dict):
    log.info(f"--- Detected {len(new_jobs)} new job(s)! ---")
    for job_id, job in new_jobs.items():
        title = job.get('job_title', 'Unknown Title')
        company = job.get('company_name', 'Unknown Company')
        vacancies = job.get('number_of_vacancies', 'N/A')

        log.info(
            f"[NEW JOB] {title} | "
            f"Company: {company} | "
            f"Vacancies: {vacancies} | "
            f"ID: {job_id}"
        )

        message = (
            "📢 <b>New SIT Job Found!</b>\n\n"
            f"💼 <b>Title:</b> {html.escape(str(title))}\n"
            f"🏢 <b>Company:</b> {html.escape(str(company))}\n"
            f"👥 <b>Vacancies:</b> {html.escape(str(vacancies))}\n"
            f"🆔 <code>{html.escape(str(job_id))}</code>\n\n"
            f'🔗 <a href="https://readytalent2.singaporetech.edu.sg/">Open ReadyTalent</a>'
        )
        await send_telegram_message(message)


#Fetches latest jobs, diffs against saved jobs, and triggers actions on new additions.

async def check_for_new_jobs():
    saved_jobs = load_saved_jobs()
    is_initial_run = len(saved_jobs) == 0 #first run was zero 

    current_jobs = await get_job_lists(initial=is_initial_run)
    if not current_jobs:
        log.warning("No jobs retrieved or fetch failed. Skipping diff check.")
        return

    saved_ids = set(saved_jobs.keys())
    current_ids = set(current_jobs.keys())
    new_ids = current_ids - saved_ids

    now_iso = datetime.now(timezone.utc).isoformat()

    if is_initial_run:
        log.info(f"Initial run: saving baseline of {len(current_jobs)} job(s) to {DATA_FILE}")
        for job_data in current_jobs.values():
            job_data["first_seen"] = now_iso
        save_jobs(current_jobs)
        return

    # Update existing jobs with latest data while keeping first_seen
    for jid, job_data in current_jobs.items():
        if jid in saved_jobs:
            job_data["first_seen"] = saved_jobs[jid].get("first_seen", now_iso)
            saved_jobs[jid] = job_data

    if new_ids:
        new_jobs = {}
        for jid in new_ids:
            job_data = current_jobs[jid]
            job_data["first_seen"] = now_iso
            new_jobs[jid] = job_data
            saved_jobs[jid] = job_data

        await handle_new_jobs(new_jobs)
        save_jobs(saved_jobs)
    else:
        # Save any updated fields for existing jobs
        save_jobs(saved_jobs)
        log.info("Check complete: No new jobs found.")


async def poll_jobs_forever(interval_seconds: int = POLL_INTERVAL_SECONDS):
    #1 hour
    log.info(f"Starting hourly job poller (interval: {interval_seconds}s)...")
    while True:
        try:
            await check_for_new_jobs()
        except Exception as e:
            log.error(f"Unexpected error during polling cycle: {e}", exc_info=True)

        log.info(f"Sleeping for {interval_seconds} seconds (~{interval_seconds // 60} minutes)...")
        await asyncio.sleep(interval_seconds)


def get_job_list(initial=False):
    return asyncio.run(get_job_lists(initial))


if __name__ == "__main__":
    try:
        asyncio.run(poll_jobs_forever())
    except KeyboardInterrupt:
        log.info("Poller stopped by user.")