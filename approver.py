import logging
import os
import requests
import subprocess
import sys

GITLAB_LABEL = "totally-human-approved"
GET_URL = f"https://git.vastdata.com/api/v4/projects/3/merge_requests/?labels={GITLAB_LABEL}&state=opened&per_page=100"
APPROVE_URL = "https://git.vastdata.com/api/v4/projects/3/merge_requests/{iid}/approve"
token = os.getenv("GITLAB_ACCESS_TOKEN")

log_path = os.path.join(os.path.dirname(__file__), "approver.log")
logging.basicConfig(filename=log_path,
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO)
logger = logging.getLogger('logger')


def get_pending_mrs():
    if not token:
        logger.error("No token found in GITLAB_ACCESS_TOKEN env var")
        return []
    response = requests.get(GET_URL, headers={"Private-Token": token})
    data = response.json()
    if response.status_code != 200:
        logger.error(f"Error getting pending merge requests: {data['message']}")
        return []
    mr_details = [dict(id=res["iid"], author=res["author"]["name"]) for res in data]
    logger.info(f"Found {len(mr_details)} pending merge requests")
    return mr_details


def approve_mr(mr_details):
    url = APPROVE_URL.format(iid=mr_details["id"])
    response = requests.post(url, headers={"Private-Token": token})
    if response.status_code != 201:
        logger.warning(f"Failed to approve merge request: {mr_details}: {response.json()}")
    else:
        logger.info(f"Approved merge request {mr_details}")


def add_to_crontab():
    # Get the path of the current script
    script_path = os.path.abspath(__file__)

    # The cron job to be added
    cron_job = f"* * * * * GITLAB_ACCESS_TOKEN={token} {sys.executable} {script_path} >> {log_path} 2>&1\n"

    # Get the current crontab
    try:
        current_crontab = subprocess.check_output("crontab -l", shell=True).decode()
    except subprocess.CalledProcessError:
        # If the crontab is empty or doesn't exist, initialize it
        current_crontab = ""

    # Check if the cron job already exists
    if cron_job not in current_crontab:
        # Add the cron job
        new_crontab = current_crontab + cron_job
        with open("temp_crontab", "w") as f:
            f.write(new_crontab)
        subprocess.run("crontab temp_crontab", shell=True)
        os.remove("temp_crontab")
        logger.info(f"Cron job added: {cron_job.strip()}")
    else:
        logger.info("Cron job already exists.")


def main():
    logger.info("=== The Auto-Approver Awakens ===")
    add_to_crontab()
    pending_mrs = get_pending_mrs()
    for mr_details in pending_mrs:
        approve_mr(mr_details)
    logger.info("=== The Auto-Approver Sleeps ===")


if __name__ == "__main__":
    main()
