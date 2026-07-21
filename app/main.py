import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks

from app.config import load_sites, save_sites
from app.database import init_db, get_recent_alerts
from app.scheduler import start_scheduler, run_check_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("govt_monitor.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    logger.info("Govt Site Monitor started.")
    yield
    logger.info("Govt Site Monitor shutting down.")


app = FastAPI(title="Govt Site Monitor", lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "running", "message": "Govt Site Monitor API"}


@app.get("/sites")
def list_sites():
    return load_sites()


@app.post("/sites")
def add_site(site: dict):
    """
    Add a new site to monitor.
    Body example:
    {
      "name": "My Site",
      "url": "https://example.gov.in/notices",
      "selector": ".notice-list",
      "enabled": true
    }
    """
    sites = load_sites()
    sites.append(site)
    save_sites(sites)
    return {"status": "added", "site": site}


@app.get("/alerts")
def alerts(limit: int = 50):
    return get_recent_alerts(limit)


@app.post("/check-now")
def check_now(background_tasks: BackgroundTasks):
    """Manually trigger a check cycle immediately, instead of waiting for the schedule."""
    background_tasks.add_task(run_check_cycle)
    return {"status": "check triggered"}


@app.get("/health")
def health():
    return {"status": "ok"}
