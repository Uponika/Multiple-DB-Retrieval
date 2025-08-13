from typing import Any, ClassVar, Dict, Optional
from langchain.tools import BaseTool
from data_access.azure_sql import get_candidate_metadata
from data_access.azure_ai_search import get_resume_by_candidate_id
from services.resume_parser import extract_profile_urls, strip_noise
from services.web_scraper import safe_scrape

class FetchCandidateContextTool(BaseTool):
    name: ClassVar[str] = "fetch_candidate_context"
    description: ClassVar[str] = "Fetch candidate metadata, resume, LinkedIn/GitHub and aggregate context"

    def _run(self, candidate_id: str) -> Dict[str, Any]:
        # candidate_id expected as a string UUID, e.g., '3e9ac460-af94-436d-9193-dd2d7b12f135'
        # If input is like "candidate_id=UUID", parse it:
        if "=" in candidate_id:
            candidate_id_str = candidate_id.split("=")[1]
        else:
            candidate_id_str = candidate_id

        metadata = get_candidate_metadata(candidate_id_str) or {}
        resume_doc = get_resume_by_candidate_id(candidate_id_str) or {}
        resume_text = strip_noise(resume_doc.get("content", ""))

        urls = extract_profile_urls(resume_text)
        public_text = "\n".join(
            filter(None, [safe_scrape(urls.get("linkedin")), safe_scrape(urls.get("github"))])
        )

        return {
            "candidate_id": candidate_id_str,
            "metadata": metadata,
            "resume_text": resume_text,
            "urls": urls,
            "public_profiles_text": public_text
        }

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("Sync only.")