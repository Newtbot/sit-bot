import asyncio
from playwright.async_api import async_playwright
from log_config import log
import os
import json
import pathlib
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

username = os.getenv("user_name")
password = os.getenv("password")

async def login(page, username, password):
    log.info("navigating to readytalent")
    await page.goto("https://readytalent2.singaporetech.edu.sg/")

    log.info("clicking Staff/Student/Alumni login")
    await page.evaluate("checkAuth()")

    log.info("waiting for ADFS page")
    await page.wait_for_load_state("networkidle", timeout=60000)

    log.info("filling credentials")
    await page.fill("#userNameInput", username)
    await page.fill("#passwordInput", password)

    log.info("submitting login")
    await page.click("#submitButton")

    await page.wait_for_load_state("networkidle", timeout=60000)
    log.info("login complete")

    await page.wait_for_timeout(5000)

#fetchs part time jobs for student only
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

#parse jobs to get SIT student work scheme
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


async def get_job_lists(initial=False):
    log.info("Starting job list retrieval")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await login(page, username , password)
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


def get_job_list(initial=False):
    return asyncio.run(get_job_lists(initial))


if __name__ == "__main__":
    get_job_list()