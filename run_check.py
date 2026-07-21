"""
Standalone entry point for running ONE check cycle and exiting.
Used by GitHub Actions (or Windows Task Scheduler, or a plain cron job) -
no always-on server needed. Each run:
  1. Loads sites from data/sites.json
  2. Checks each for new items
  3. Sends one email per site if new items were found
  4. Saves updated state to data/monitor.db (committed back to the repo by
     the GitHub Actions workflow so state persists between runs)
"""
import logging

from app.database import init_db
from app.scheduler import run_check_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

if __name__ == "__main__":
    init_db()
    run_check_cycle()
