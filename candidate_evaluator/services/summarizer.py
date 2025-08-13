import json
from typing import Dict
from langchain_openai import ChatOpenAI
from prompts.summarizer_prompt import SUMMARIZER_TEMPLATE
from dotenv import load_dotenv
import os
load_dotenv(override=True)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key= os.getenv("OPENAI_API_KEY"))

def summarize_candidate(content: str) -> Dict:
    combined_content = f"""

Resume:
{content}

"""
    prompt = SUMMARIZER_TEMPLATE.format(content=combined_content)
    raw = llm.predict(prompt)
    try:
        return json.loads(raw)
    except Exception:
        # Minimal fallback
        return {
            "work_experience_summary": "",
            "skills_summary": "",
            "education_summary": "",
            "projects_summary": "",
            "linkedin": "Not found",
            "github": "Not found",
        }
