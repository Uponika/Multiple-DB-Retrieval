import streamlit as st
import pandas as pd
from data_access.azure_sql import list_all_candidate_ids
from agents.resume_agent import evaluate_candidates
from data_access.azure_ai_search import search_resumes_by_text
from dotenv import load_dotenv
import os
load_dotenv(override=True)

st.set_page_config(page_title="Agentic Candidate Evaluator", layout="wide")
st.title("🔎 Agentic Candidate Evaluator")

tab1, tab2 = st.tabs(["🔍 Semantic Search", "🏅 Rank Candidates"])

with tab1:
    q = st.text_input("Search resumes (semantic text):", placeholder="e.g., Azure Functions FastAPI microservices")
    if st.button("Search"):
        docs = search_resumes_by_text(q, top=5)
        st.subheader("Top Matches")
        for d in docs:
            st.markdown(f"**candidate_id:** `{d.get('candidate_id')}` — **score:** {d.get('@search.score'):.2f}")
            st.code((d.get("content") or "")[:800] + ("..." if len(d.get('content',''))>800 else ""))

with tab2:
    st.write("Provide job requirements (used for summary + scoring).")
    reqs = st.text_area("Job requirements", height=160, placeholder="e.g., 5+ years Python, Azure, FastAPI, vector databases, LangChain; Kubernetes is a plus.")
    run = st.button("Evaluate & Rank All Candidates")

    if run:
        with st.spinner("Evaluating candidates..."):
            cids = list_all_candidate_ids()
            ranked = evaluate_candidates(cids, reqs)

        # Table
        table = pd.DataFrame([{
            "candidate_id": r["candidate_id"],
            "name": r["name"],
            "location": r["location"],
            "status": r["status"],
            "score": r["score"]
        } for r in ranked])
        st.subheader("Ranking")
        st.dataframe(table, use_container_width=True)

        # Details
        for r in ranked:
            with st.expander(f"{r['name']} — Score {r['score']} — ({r['candidate_id']})"):
                st.markdown(f"**Email:** {r['email']}  |  **Location:** {r['location']}  |  **Status:** {r['status']}")
                st.markdown(f"**LinkedIn:** {r['summary'].get('linkedin')}")
                st.markdown(f"**GitHub:** {r['summary'].get('github')}")
                st.markdown("**Work Experience**")
                st.write(r["summary"].get("work_experience_summary", ""))
                st.markdown("**Skills**")
                st.write(r["summary"].get("skills_summary", ""))
                st.markdown("**Education**")
                st.write(r["summary"].get("education_summary", ""))
                st.markdown("**Projects**")
                st.write(r["summary"].get("projects_summary", ""))
                st.markdown("**Why this score?**")
                st.write(r.get("rationale", ""))
































# from azure.search.documents import SearchClient
# from azure.core.credentials import AzureKeyCredential
# import pyodbc
# import streamlit as st
# from dotenv import load_dotenv
# import os
# from openai import OpenAI
# import re
# import json
# import pandas as pd


# load_dotenv()

# search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
# search_key = os.getenv("AZURE_SEARCH_API_KEY")
# search_index = os.getenv("AZURE_SEARCH_INDEX")

# search_client = SearchClient(
#     endpoint=search_endpoint,
#     index_name=search_index,
#     credential=AzureKeyCredential(search_key)
# )

# server = os.getenv("server").strip()
# database = os.getenv("database").strip()
# sql_username = os.getenv("sql_username").strip()
# password = os.getenv("password").strip()
# driver = os.getenv("driver").strip()


# sql_conn = pyodbc.connect(
#     f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
# )
# cursor = sql_conn.cursor()

# client = OpenAI(api_key = os.getenv("OPENAI_API_KEY"))


# ALLOWED_COLUMNS = {"candidate_id", "name", "location", "email", "status"}
# ALLOWED_OPERATORS = {
#     "=", "like", "and", "or", "where", ">", "<", ">=", "<=", "not", "in"
# }
# def classify_query_llm(query: str) -> str:
#     """
#     Uses LLM to classify the query as 'sql', 'vector', or 'both'.
#     """
#     prompt = f"""
#     You are a routing engine for a candidate search app.
#     - SQL: for structured data like candidate name, location, email, status.
#     - Vector: for searching semantic content of resumes.
#     - Both: if the query requires both structured and semantic search.

#     Only respond with one word: sql, vector, or both.
#     Query: "{query}"
#     Category:
#     """
#     response = client.chat.completions.create(
#         model="gpt-4o-mini",  # fast and cheap
#         messages=[{"role": "system", "content": "You are a helpful query router."},
#                   {"role": "user", "content": prompt}],
#         temperature=0
#     )
#     return response.choices[0].message.content.strip().lower()


# # --- Helper: get candidate_ids from SQL search ---
# def get_candidate_ids_by_name(name_query):
#     name_parts = name_query.strip().split()
#     patterns = [f"%{part}%" for part in name_parts]

#     # Use OR instead of AND here
#     sql = """
#     SELECT candidate_id, name FROM candidates
#     WHERE """ + " OR ".join(
#         ["(LOWER(name) LIKE LOWER(?) OR LOWER(email) LIKE LOWER(?))"] * len(name_parts)
#     )

#     params = []
#     for p in patterns:
#         params.extend([p, p])

#     cursor.execute(sql, params)
#     rows = cursor.fetchall()

#     return [r[0] for r in rows]


# #---- Vector search without filtering-----
# def search_vector(query):
#     results = search_client.search(
#         search_text=query,
#         top=3
#     )
#     return [{"candidate_id": r["candidate_id"], "content": r["content"]} for r in results]

# # --- Extract candidate name from query using LLM ---
# def extract_candidate_name(query: str) -> str:
#     prompt = f"""
#         Extract only the candidate's full name from the following query.  
#         If there is no name, respond with an empty string.

#         Query: "{query}"
#         Candidate Name:
#         """
#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "You extract candidate names from queries."},
#             {"role": "user", "content": prompt},
#         ],
#         temperature=0,
#     )
#     name = response.choices[0].message.content.strip()
#     return name
# # --- Vector search filtered by candidate_id ---
# def search_vector_for_candidates(query, candidate_ids):
#     if not candidate_ids:
#         # fallback: no filter
#         return search_vector(query)

#     # Detect if candidate_id field is string or int
#     # For demo assume string
#     filter_expr = " or ".join([f"candidate_id eq '{cid}'" for cid in candidate_ids])

#     results = search_client.search(
#         search_text=query,
#         filter=filter_expr,
#         top=3
#     )
#     return [{"candidate_id": r["candidate_id"], "content": r["content"]} for r in results]


# # ===== Safe SQL Search =====
# def is_safe_clause(where_clause: str) -> bool:
#     clause = where_clause.lower()

#     # Block dangerous keywords and characters
#     forbidden_keywords = ["drop", "delete", "update", "insert", "alter", "truncate", ";", "--", "union", "exec", "execute"]
#     if any(word in clause for word in forbidden_keywords):
#         return False

#     # Remove string literals to avoid false token matches
#     clause_no_strings = re.sub(r"'[^']*'", "", clause)

#     # Extract tokens: words, operators, parentheses, commas, numbers, %
#     tokens = re.findall(r"[a-zA-Z_]+|[><=]+|%+|\(|\)|,|\d+", clause_no_strings)

#     for token in tokens:
#         token = token.strip()
#         if not token:
#             continue
#         # Allow parentheses and commas as tokens
#         if token in ("(", ")", ","):
#             continue
#         # Allow numbers
#         if token.isdigit():
#             continue
#         # Check if alphabetic token is allowed
#         if token.isalpha():
#             if token not in ALLOWED_COLUMNS and token not in ALLOWED_OPERATORS:
#                 return False
#         else:
#             # For operators like >=, <=, =, etc., assume safe if part of allowed operators
#             # They are captured above as separate tokens, so you can skip or allow here
#             continue

#     return True
# # ===== SQL Search =====
# def search_sql(query):
#     sql_prompt = f"""
#         You are an expert SQL generator for the 'candidates' table with columns:
#         candidate_id, name, location, email, status.

#         For this natural language query, output TWO things exactly in this format:

#         SELECT: column1, column2, ...
#         WHERE: <where clause>

#         The SELECT line should contain only the columns the user is requesting.

#         The WHERE line should be a safe SQL WHERE clause filtering the candidates.

#         Only output these two lines exactly, no extra text.

#         Query: "{query}"
#     """

#     response_text = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "You are a SQL query generator."},
#             {"role": "user", "content": sql_prompt}
#         ],
#         temperature=0,
#     ).choices[0].message.content.strip()

#     st.write("LLM SQL output:", response_text)  # debug

#     # Parse the response
#     select_line = None
#     where_line = None
#     for line in response_text.splitlines():
#         line = line.strip()
#         if line.lower().startswith("select:"):
#             select_line = line[len("select:"):].strip()
#         elif line.lower().startswith("where:"):
#             where_line = line[len("where:"):].strip()

#     if not select_line or not where_line:
#         return [{"error": "Failed to parse LLM response"}]

#     # Validate columns in SELECT
#     selected_columns = [col.strip() for col in select_line.split(",")]
#     for col in selected_columns:
#         if col not in ALLOWED_COLUMNS:
#             return [{"error": f"Invalid column requested: {col}"}]

#     # Validate WHERE clause safely
#     if not is_safe_clause(where_line):
#         return [{"error": "Unsafe SQL detected, query aborted."}]

#     sql = f"SELECT {', '.join(selected_columns)} FROM candidates WHERE {where_line}"
#     cursor.execute(sql)
#     rows = cursor.fetchall()

#     # Build response dicts dynamically based on selected columns
#     results = []
#     for row in rows:
#         result = {}
#         for idx, col in enumerate(selected_columns):
#             result[col] = row[idx]
#         results.append(result)

#     return results

# # --- LLM answer synthesis ---
# def synthesize_answer(user_query, sql_results, vector_results):
#     prompt = f"""
#         You are an expert assistant that answers candidate queries precisely.

#         Candidate Info (from SQL): {sql_results}

#         Relevant Resume Excerpts (from semantic search): {vector_results}

#         User Question: {user_query}

#         Based on the above, provide a concise and accurate answer focused only on the candidate(s) in question.
#         """
#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "You answer candidate questions based on given data."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0,
#     )
#     return response.choices[0].message.content.strip()


# # --- Modified search flow in Streamlit ---
# st.title("LLM-Based Candidate Search")

# user_query = st.text_input("Enter your query:")

# if st.button("Search") and user_query:
#     route = classify_query_llm(user_query)
#     st.write(f"**LLM decided route:** `{route}`")

#     sql_results = []
#     vector_results = []
#     final_answer = None

#     if route in ["sql", "both"]:
#         sql_results = search_sql(user_query)
#         st.subheader("SQL Search Results")
#         st.write(sql_results)

#     if route in ["vector", "both"]:
        
#         candidate_name = extract_candidate_name(user_query)
#         if candidate_name:
#             candidate_ids = get_candidate_ids_by_name(candidate_name)
#             if candidate_ids:
#                 vector_results = search_vector_for_candidates(user_query, candidate_ids)
#             else:
#                 vector_results = search_vector(user_query)
#         else:
#             vector_results = search_vector(user_query)

#         st.subheader("Vector Search Results")
#         st.write(vector_results)

#         # If both results available, synthesize final answer
#         if route == "both":
#             final_answer = synthesize_answer(user_query, sql_results, vector_results)
#             st.subheader("Final Synthesized Answer")
#             st.write(final_answer)
