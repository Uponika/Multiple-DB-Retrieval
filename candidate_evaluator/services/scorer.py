import json
from typing import Dict
from langchain_openai import ChatOpenAI
from prompts.scoring_prompt import SCORING_TEMPLATE
from dotenv import load_dotenv
import os
load_dotenv(override=True)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key= os.getenv("OPENAI_API_KEY"))

def score_candidate(summary_json: Dict, job_requirements: str) -> Dict:
    prompt = SCORING_TEMPLATE.format(
        summary=json.dumps(summary_json, indent=2),
        requirements=job_requirements or "General software engineering role."
    )
    raw = llm.predict(prompt)
    try:
        obj = json.loads(raw)
        if "candidate_score" not in obj:
            obj["candidate_score"] = 0
        return obj
    except Exception:
        return {"candidate_score": 0, "rationale": "Failed to parse scoring output."}
