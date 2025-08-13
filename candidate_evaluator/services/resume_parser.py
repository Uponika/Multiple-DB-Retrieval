import re
from typing import List, Dict

URL_RE = re.compile(r"(https?://[^\s)]+)")

def extract_profile_urls(resume_text: str) -> Dict[str, str]:
    urls = URL_RE.findall(resume_text or "")
    linkedin = next((u for u in urls if "linkedin.com" in u.lower()), None)
    github   = next((u for u in urls if "github.com"   in u.lower()), None)
    return {"linkedin": linkedin, "github": github}

def strip_noise(text: str) -> str:
    if not text:
        return ""
    # Tiny cleanup; expand as needed
    return re.sub(r"\s+\n", "\n", text).strip()
