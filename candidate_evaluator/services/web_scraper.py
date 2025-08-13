from typing import Optional
import requests
from bs4 import BeautifulSoup
from config.settings import HTTP_TIMEOUT_SEC, ALLOW_PUBLIC_SCRAPE

def safe_scrape(url: Optional[str]) -> str:
    if not url:
        return ""
    if not ALLOW_PUBLIC_SCRAPE:
        # Respect ToS / your compliance posture; skip scraping unless env flag set.
        return ""
    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT_SEC, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Return visible text
        return soup.get_text(separator="\n")
    except Exception:
        return ""
