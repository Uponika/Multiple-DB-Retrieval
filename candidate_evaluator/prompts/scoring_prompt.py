SCORING_TEMPLATE = """You are a hiring evaluator.
Given the structured SUMMARY (JSON) and JOB REQUIREMENTS (plain text),
assign a candidate_score from 0-100. Consider:
- Skill match (40%)
- Relevant years/roles/industries (30%)
- Education relevance (10%)
- Projects impact & recency (10%)
- Public profile activity/quality (10%)

Return JSON: {{"candidate_score": <int>, "rationale": "<one paragraph>"}}.

SUMMARY:
{summary}

JOB REQUIREMENTS:
{requirements}
"""
