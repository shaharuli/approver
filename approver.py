import logging
import os
import requests
import subprocess
import sys
from logging.handlers import TimedRotatingFileHandler

GET_URL = "https://git.vastdata.com/api/v4/projects/3/merge_requests/?reviewer_username={reviewer}&state=opened&per_page=100"
APPROVE_URL = "https://git.vastdata.com/api/v4/projects/3/merge_requests/{iid}/approve"
FIGHT_CLUB_MEMBERS_URL = "https://git.vastdata.com/api/v4/projects/3/merge_requests/185950"
token = os.getenv("GITLAB_ACCESS_TOKEN")

log_path = os.path.join(os.path.dirname(__file__), "approver.log")
handler = TimedRotatingFileHandler(log_path, when='W0', interval=1, backupCount=2)
handler.setFormatter(logging.Formatter('%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s'))
logger = logging.getLogger('logger')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def get_club_members() -> set[str]:
    response = requests.get(FIGHT_CLUB_MEMBERS_URL, headers={"Private-Token": token})
    data = response.json()
    if response.status_code != 200:
        logger.error(f"Error getting fight club members: {data['message']}")
        return set()
    members = {reviewer["name"] for reviewer in data["reviewers"]}
    logger.info(f"Found {len(members)} fight club members: {members}")
    return members


def get_pending_mrs() -> list[int]:
    if not token:
        logger.error("No token found in GITLAB_ACCESS_TOKEN env var")
        return []
    local_user = get_local_git_user()
    club_members = get_club_members()
    club_members.discard(local_user)
    response = requests.get(GET_URL.format(reviewer=local_user), headers={"Private-Token": token})
    data = response.json()
    if response.status_code != 200:
        logger.error(f"Error getting pending merge requests: {data['message']}")
        return []
    # Get local user to avoid trying to approve your own merge requests
    mr_ids = [res["iid"] for res in data if res["author"]["name"] in club_members]
    logger.info(f"Found {len(mr_ids)} pending merge requests")
    return mr_ids


def approve_mr(mr_id: int):
    url = APPROVE_URL.format(iid=mr_id)
    response = requests.post(url, headers={"Private-Token": token})
    if response.status_code != 201:
        logger.warning(f"Failed to approve merge request: {mr_id}: {response.json()}")
    else:
        logger.info(f"Approved merge request {mr_id}")


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


def get_local_git_user() -> str:
    try:
        res = subprocess.check_output(["git", "config", "user.email"])
        return res.decode().strip().split("@")[0]
    except Exception as e:
        logger.error(f"Failed to get local git user: {e}")
        return ""


def main():
    logger.info("=== The Auto-Approver Awakens ===")
    add_to_crontab()
    pending_mrs = get_pending_mrs()
    for mr_id in pending_mrs:
        approve_mr(mr_id)
    logger.info("=== The Auto-Approver Sleeps ===")


if __name__ == "__main__":
    main()
