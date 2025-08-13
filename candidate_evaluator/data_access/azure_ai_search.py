from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from config.settings import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY, AZURE_SEARCH_INDEX

def _client() -> SearchClient:
    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )

def search_resumes_by_text(query: str, top: int = 5) -> List[Dict[str, Any]]:
    sc = _client()
    results = sc.search(search_text=query, top=top)
    return [dict(r) for r in results]

def get_resume_by_candidate_id(candidate_id: str) -> Optional[Dict[str, Any]]:
    sc = _client()
    filter_expr = f"candidate_id eq '{candidate_id.strip('{}')}'"
    results = list(sc.search(search_text="", filter=filter_expr, top=1, select=["content"]))
    print(f"Search results for candidate_id={candidate_id}: {results}")
    if not results:
        return None

    doc = results[0]
    return {
        "resume_text": doc.get("content", ""),
        "metadata": {},  # fill if available
        "public_profiles_text": "",  # fill if available
    }






 