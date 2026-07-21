import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import CHECK_INTERVAL_MINUTES, load_sites
from app.database import get_known_titles, update_site_state, log_alert
from app.mailer import send_new_items_email
from app.scraper import check_site_for_change, compute_hash
from app.summarizer import summarize_new_items

logger = logging.getLogger("govt_monitor.scheduler")

scheduler = BackgroundScheduler()


def run_check_cycle():
    """Checks every enabled site once, and if new items appeared, emails them all in one go."""
    sites = load_sites()
    logger.info(f"Running check cycle for {len(sites)} site(s)...")

    for site in sites:
        name = site["name"]
        try:
            previous_titles = get_known_titles(name)
            new_items, is_first_check, all_items, plain_text = check_site_for_change(
                site, previous_titles
            )
            text_hash = compute_hash(plain_text)

            if is_first_check:
                logger.info(
                    f"[{name}] First check - baseline saved "
                    f"({len(all_items)} item(s) found). No alert sent."
                )
                update_site_state(name, site["url"], all_items, text_hash)
                continue

            if not new_items:
                logger.info(f"[{name}] No new items detected.")
                update_site_state(name, site["url"], all_items, text_hash)
                continue

            logger.info(f"[{name}] {len(new_items)} new item(s) detected! Summarizing...")
            blurbs = summarize_new_items(name, new_items)

            items_with_blurbs = [
                {"title": it["title"], "url": it["url"], "blurb": blurb}
                for it, blurb in zip(new_items, blurbs)
            ]

            emailed = send_new_items_email(name, site["url"], items_with_blurbs)

            for it in items_with_blurbs:
                log_alert(name, it["title"], it["url"], it["blurb"], emailed)

            update_site_state(name, site["url"], all_items, text_hash)

        except Exception as e:
            logger.error(f"[{name}] Error during check: {e}")


def start_scheduler():
    scheduler.add_job(
        run_check_cycle,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        id="site_check_job",
        next_run_time=None,  # first run triggered manually in main.py startup
    )
    scheduler.start()
    logger.info(f"Scheduler started - checking every {CHECK_INTERVAL_MINUTES} minutes.")
