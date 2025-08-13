from typing import List, Dict, Any
from langchain.agents import AgentExecutor, initialize_agent
from langchain_openai import ChatOpenAI
from .tools import FetchCandidateContextTool
from services.summarizer import summarize_candidate
from services.scorer import score_candidate
from dotenv import load_dotenv
import os
load_dotenv(override=True)

def build_agent():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key = os.getenv("OPENAI_API_KEY"))
    tools = [FetchCandidateContextTool()]
    # zero-shot-react description is fine here since we mainly use a single tool
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent="zero-shot-react-description",
        verbose=False,
        handle_parsing_errors=True,
    )
    return agent

def evaluate_candidates(candidate_ids: List[str], job_requirements: str) -> List[Dict[str, Any]]:
    """
    Orchestrates context fetch -> summarize -> score for each candidate_id.
    Returns a list sorted by candidate_score (desc).
    """
    agent = build_agent()
    results = []

    for cid in candidate_ids:
        # 1) Agent fetches context via tool
        context = agent.run(f"Fetch full context for candidate_id={cid}")
        # agent.run returns a string; tool returned a dict → langchain will stringify it.
        # Be robust to both cases:
        if isinstance(context, str):
            # naive eval-safe parse attempt
            try:
                import json, ast
                context_obj = json.loads(context)
            except Exception:
                try:
                    context_obj = ast.literal_eval(context)
                except Exception:
                    context_obj = {"resume_text": "", "metadata": {}, "urls": {}, "public_profiles_text": ""}
        else:
            context_obj = context

        metadata = context_obj.get("metadata", {})
        resume_text = context_obj.get("resume_text", "")
        public_profiles_text = context_obj.get("public_profiles_text", "")
        urls = context_obj.get("urls", {})

        # 2) Summarize
        summary = summarize_candidate(resume_text)
        # ensure links
        summary["linkedin"] = summary.get("linkedin") or urls.get("linkedin") or "Not found"
        summary["github"]   = summary.get("github")   or urls.get("github")   or "Not found"

        # 3) Score
        score_obj = score_candidate(summary, job_requirements)

        results.append({
            "candidate_id": cid,
            "name": metadata.get("name"),
            "location": metadata.get("location"),
            "email": metadata.get("email"),
            "status": metadata.get("status"),
            "summary": summary,
            "score": score_obj.get("candidate_score", 0),
            "rationale": score_obj.get("rationale", "")
        })

    # Sort by score desc
    results.sort(key=lambda r: r["score"], reverse=True)
    return results
