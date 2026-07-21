import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SITES_FILE = BASE_DIR / "data" / "sites.json"

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
MAIL_TO = os.getenv("MAIL_TO", "")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "data/monitor.db")


def load_sites():
    """Load the list of sites to monitor from data/sites.json"""
    with open(SITES_FILE, "r", encoding="utf-8") as f:
        sites = json.load(f)
    return [s for s in sites if s.get("enabled", True)]


def save_sites(sites):
    with open(SITES_FILE, "w", encoding="utf-8") as f:
        json.dump(sites, f, indent=2, ensure_ascii=False)
