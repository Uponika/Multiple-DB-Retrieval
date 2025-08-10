from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import pyodbc
import streamlit as st
from dotenv import load_dotenv
import os
from openai import OpenAI
import re
import json
import pandas as pd


load_dotenv()

search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_SEARCH_API_KEY")
search_index = os.getenv("AZURE_SEARCH_INDEX")

search_client = SearchClient(
    endpoint=search_endpoint,
    index_name=search_index,
    credential=AzureKeyCredential(search_key)
)

server = os.getenv("server").strip()
database = os.getenv("database").strip()
sql_username = os.getenv("sql_username").strip()
password = os.getenv("password").strip()
driver = os.getenv("driver").strip()


sql_conn = pyodbc.connect(
    f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)
cursor = sql_conn.cursor()

client = OpenAI(api_key = os.getenv("OPENAI_API_KEY"))


ALLOWED_COLUMNS = {"candidate_id", "name", "location", "email", "status"}
ALLOWED_OPERATORS = {
    "=", "like", "and", "or", "where", ">", "<", ">=", "<=", "not", "in"
}
def classify_query_llm(query: str) -> str:
    """
    Uses LLM to classify the query as 'sql', 'vector', or 'both'.
    """
    prompt = f"""
    You are a routing engine for a candidate search app.
    - SQL: for structured data like candidate name, location, email, status.
    - Vector: for searching semantic content of resumes.
    - Both: if the query requires both structured and semantic search.

    Only respond with one word: sql, vector, or both.
    Query: "{query}"
    Category:
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # fast and cheap
        messages=[{"role": "system", "content": "You are a helpful query router."},
                  {"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content.strip().lower()


# --- Helper: get candidate_ids from SQL search ---
def get_candidate_ids_by_name(name_query):
    name_parts = name_query.strip().split()
    patterns = [f"%{part}%" for part in name_parts]

    # Use OR instead of AND here
    sql = """
    SELECT candidate_id, name FROM candidates
    WHERE """ + " OR ".join(
        ["(LOWER(name) LIKE LOWER(?) OR LOWER(email) LIKE LOWER(?))"] * len(name_parts)
    )

    params = []
    for p in patterns:
        params.extend([p, p])

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    return [r[0] for r in rows]


#---- Vector search without filtering-----
def search_vector(query):
    results = search_client.search(
        search_text=query,
        top=3
    )
    return [{"candidate_id": r["candidate_id"], "content": r["content"]} for r in results]

# --- Extract candidate name from query using LLM ---
def extract_candidate_name(query: str) -> str:
    prompt = f"""
        Extract only the candidate's full name from the following query.  
        If there is no name, respond with an empty string.

        Query: "{query}"
        Candidate Name:
        """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You extract candidate names from queries."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    name = response.choices[0].message.content.strip()
    return name
# --- Vector search filtered by candidate_id ---
def search_vector_for_candidates(query, candidate_ids):
    if not candidate_ids:
        # fallback: no filter
        return search_vector(query)

    # Detect if candidate_id field is string or int
    # For demo assume string
    filter_expr = " or ".join([f"candidate_id eq '{cid}'" for cid in candidate_ids])

    results = search_client.search(
        search_text=query,
        filter=filter_expr,
        top=3
    )
    return [{"candidate_id": r["candidate_id"], "content": r["content"]} for r in results]


# ===== Safe SQL Search =====
def is_safe_clause(where_clause: str) -> bool:
    clause = where_clause.lower()

    # Block dangerous keywords and characters
    forbidden_keywords = ["drop", "delete", "update", "insert", "alter", "truncate", ";", "--", "union", "exec", "execute"]
    if any(word in clause for word in forbidden_keywords):
        return False

    # Remove string literals to avoid false token matches
    clause_no_strings = re.sub(r"'[^']*'", "", clause)

    # Extract tokens: words, operators, parentheses, commas, numbers, %
    tokens = re.findall(r"[a-zA-Z_]+|[><=]+|%+|\(|\)|,|\d+", clause_no_strings)

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        # Allow parentheses and commas as tokens
        if token in ("(", ")", ","):
            continue
        # Allow numbers
        if token.isdigit():
            continue
        # Check if alphabetic token is allowed
        if token.isalpha():
            if token not in ALLOWED_COLUMNS and token not in ALLOWED_OPERATORS:
                return False
        else:
            # For operators like >=, <=, =, etc., assume safe if part of allowed operators
            # They are captured above as separate tokens, so you can skip or allow here
            continue

    return True
# ===== SQL Search =====
def search_sql(query):
    sql_prompt = f"""
        You are an expert SQL generator for the 'candidates' table with columns:
        candidate_id, name, location, email, status.

        For this natural language query, output TWO things exactly in this format:

        SELECT: column1, column2, ...
        WHERE: <where clause>

        The SELECT line should contain only the columns the user is requesting.

        The WHERE line should be a safe SQL WHERE clause filtering the candidates.

        Only output these two lines exactly, no extra text.

        Query: "{query}"
    """

    response_text = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a SQL query generator."},
            {"role": "user", "content": sql_prompt}
        ],
        temperature=0,
    ).choices[0].message.content.strip()

    st.write("LLM SQL output:", response_text)  # debug

    # Parse the response
    select_line = None
    where_line = None
    for line in response_text.splitlines():
        line = line.strip()
        if line.lower().startswith("select:"):
            select_line = line[len("select:"):].strip()
        elif line.lower().startswith("where:"):
            where_line = line[len("where:"):].strip()

    if not select_line or not where_line:
        return [{"error": "Failed to parse LLM response"}]

    # Validate columns in SELECT
    selected_columns = [col.strip() for col in select_line.split(",")]
    for col in selected_columns:
        if col not in ALLOWED_COLUMNS:
            return [{"error": f"Invalid column requested: {col}"}]

    # Validate WHERE clause safely
    if not is_safe_clause(where_line):
        return [{"error": "Unsafe SQL detected, query aborted."}]

    sql = f"SELECT {', '.join(selected_columns)} FROM candidates WHERE {where_line}"
    cursor.execute(sql)
    rows = cursor.fetchall()

    # Build response dicts dynamically based on selected columns
    results = []
    for row in rows:
        result = {}
        for idx, col in enumerate(selected_columns):
            result[col] = row[idx]
        results.append(result)

    return results

# --- LLM answer synthesis ---
def synthesize_answer(user_query, sql_results, vector_results):
    prompt = f"""
        You are an expert assistant that answers candidate queries precisely.

        Candidate Info (from SQL): {sql_results}

        Relevant Resume Excerpts (from semantic search): {vector_results}

        User Question: {user_query}

        Based on the above, provide a concise and accurate answer focused only on the candidate(s) in question.
        """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You answer candidate questions based on given data."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


# --- Modified search flow in Streamlit ---
st.title("LLM-Based Candidate Search")

user_query = st.text_input("Enter your query:")

if st.button("Search") and user_query:
    route = classify_query_llm(user_query)
    st.write(f"**LLM decided route:** `{route}`")

    sql_results = []
    vector_results = []
    final_answer = None

    if route in ["sql", "both"]:
        sql_results = search_sql(user_query)
        st.subheader("SQL Search Results")
        st.write(sql_results)

    if route in ["vector", "both"]:
        
        candidate_name = extract_candidate_name(user_query)
        if candidate_name:
            candidate_ids = get_candidate_ids_by_name(candidate_name)
            if candidate_ids:
                vector_results = search_vector_for_candidates(user_query, candidate_ids)
            else:
                vector_results = search_vector(user_query)
        else:
            vector_results = search_vector(user_query)

        st.subheader("Vector Search Results")
        st.write(vector_results)

        # If both results available, synthesize final answer
        if route == "both":
            final_answer = synthesize_answer(user_query, sql_results, vector_results)
            st.subheader("Final Synthesized Answer")
            st.write(final_answer)

























# # IMPORTANT: adjust this to the actual metadata columns in your candidates table
# ALLOWED_COLUMNS = {
#     "status": "status",
#     "location": "location",
#     "name": "name",
#     "email": "email",    
#     "candidate_id": "candidate_id"    
# }


# def classify_query_intent_llm(query: str) -> str:
#     prompt = f"""
#         You are an intent classification assistant for a candidate search app.

#         - resume_search: questions about skills, technologies, experiences, tools, programming languages, qualifications, certifications, or anything in the full resume text.
#         - metadata_search: questions about fixed candidate attributes stored in metadata: name, email, phone, location, status, interview status, candidate ID.

#         If the query asks about what a candidate knows, their skills, or experience, classify it as resume_search.

#         Classify the following query into exactly one label: resume_search or metadata_search.

#         Query: "{query}"
#         Answer with exactly one word: resume_search or metadata_search.
#         """
#     resp = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "You are an intent classification assistant."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0
#     )
#     intent = resp.choices[0].message.content.strip().lower()
#     if intent not in ("resume_search", "metadata_search"):
#         intent = "resume_search"
#     return intent

# def extract_metadata_filter(query: str) -> tuple:
#     # 1. Try explicit 'col = val'
#     explicit = re.search(r"([a-zA-Z0-9_ ]+)\s*=\s*['\"]?([^'\"]+)['\"]?", query)
#     if explicit:
#         col = explicit.group(1).strip().lower().replace(" ", "_")
#         val = explicit.group(2).strip()
#         return col, val

#     # 2. Quick fallback for "from <location>"
#     from_match = re.search(r"from ([a-zA-Z ]+)", query, re.IGNORECASE)
#     if from_match:
#         val = from_match.group(1).strip()
#         return "location", val

#     # 3. Heuristic for "give/list <column> of all candidates"
#     all_cols_pattern = "|".join(ALLOWED_COLUMNS.keys())
#     all_match = re.search(rf"(?:give|list|show|get)\s+({all_cols_pattern})\s+of\s+all\s+candidates", query, re.IGNORECASE)
#     if all_match:
#         col = all_match.group(1).strip().lower().replace(" ", "_")
#         return col, None  # No filter value - means get column for all

#     # 4. Fallback to LLM extraction (your existing code)...
#     allowed_list = ", ".join(list(ALLOWED_COLUMNS.keys()))
#     prompt = f"""
#             Extract a single metadata filter from the user's query. Allowed columns: {allowed_list}.
#             Return JSON ONLY with keys "column" and "value".
#             If no usable filter found, return {{"column": null, "value": null}}.

#             Examples:
#             - "list all candidates from toronto" -> {{"column":"location","value":"Toronto"}}
#             - "show candidates interviewed last month" -> {{"column":"status","value":"Interviewed"}}
#             - "get emails of shortlisted candidates" -> {{"column":"status","value":"Shortlisted"}}

#             Now extract from this query:
#             "{query}"
#             """
#     resp = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "You are a JSON extractor that returns a single filter."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0
#     )
#     try:
#         out = resp.choices[0].message.content.strip()
#         parsed = json.loads(out)
#     except Exception:
#         try:
#             parsed = json.loads(out.replace("'", '"'))
#         except Exception:
#             return None, None

#     col = parsed.get("column")
#     val = parsed.get("value")
#     if col:
#         col = col.strip().lower().replace(" ", "_")
#     return col, val

# def query_azure_ai_search(query_text: str, candidate_id: str = None) -> list:
#     client_search = SearchClient(
#         endpoint=search_endpoint,
#         index_name=index_name,
#         credential=AzureKeyCredential(search_key)
#     )
#     # If candidate_id given, filter on it for exact resume search
#     if candidate_id:
#         results = client_search.search(
#             search_text=query_text,
#             filter=f"candidate_id eq '{candidate_id}'",
#             top=5,
#             select=["candidate_id", "content"]
#         )
#     else:
#         results = client_search.search(
#             search_text=query_text,
#             top=5,
#             select=["candidate_id", "content"]
#         )
#     hits = []
#     for result in results:
#         hits.append({
#             "candidate_id": result.get("candidate_id"),
#             "content": result.get("content", ""),
#             "score": result.get("@search.score")
#         })
#     return hits

# def query_azure_sql_db(filter_column: str, filter_value: str) -> list:
#     connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

#     conn = pyodbc.connect(connection_string)
#     cursor = conn.cursor()

#     # Use LOWER(...) = LOWER(?) for case-insensitive
#     sql = f"SELECT * FROM candidates WHERE LOWER({filter_column}) = LOWER(?)"
#     cursor.execute(sql, filter_value)

#     rows = cursor.fetchall()
#     cols = [column[0] for column in cursor.description] if cursor.description else []
#     results = [dict(zip(cols, row)) for row in rows]

#     cursor.close()
#     conn.close()
#     return results

# def get_candidate_id_by_name(name: str) -> str | None:
#     connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

#     conn = pyodbc.connect(connection_string)
#     cursor = conn.cursor()

#     query = "SELECT candidate_id FROM candidates WHERE LOWER(name) = LOWER(?)"
#     cursor.execute(query, name)

#     row = cursor.fetchone()
#     cursor.close()
#     conn.close()

#     if row:
#         return row[0]  # candidate_id
#     return None


# def query_azure_sql_db_no_filter(select_column: str) -> list:
#     connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
#     conn = pyodbc.connect(connection_string)
#     cursor = conn.cursor()

#     # Sanitize column name to avoid SQL injection (only allowed columns)
#     if select_column not in ALLOWED_COLUMNS.values():
#         return []

#     sql = f"SELECT {select_column} FROM candidates"
#     cursor.execute(sql)

#     rows = cursor.fetchall()
#     cols = [column[0] for column in cursor.description] if cursor.description else []
#     results = [dict(zip(cols, row)) for row in rows]

#     cursor.close()
#     conn.close()
#     return results
# # Streamlit UI
# st.title("Candidate Search App")

# user_query = st.text_input("Ask anything about candidates or resumes:")

# if user_query:
#     intent = classify_query_intent_llm(user_query)
#     st.write(f"Detected intent: **{intent}**")

#     if intent == "resume_search":
#         # Detect "skills of Alice" style queries and extract name
#         name_match = re.search(
#         r"(?:skills|experience|resume|projects|worked) of ([a-zA-Z]+(?: [a-zA-Z]+)*)",
#         user_query,
#         re.IGNORECASE,
#         )
#         if name_match:
#             person_name = name_match.group(1).strip("?.! ")
#             candidate_id = get_candidate_id_by_name(person_name)
#             if candidate_id:
#                 # Search Azure Cognitive Search, filtered to this candidate_id
#                 hits = query_azure_ai_search(user_query, candidate_id=candidate_id)
#                 st.subheader(f"Resume Search Results for {person_name}")
#                 if hits:
#                     for h in hits:
#                         st.write(f"Candidate ID: {h['candidate_id']}, Score: {h['score']}")
#                         st.write(h['content'][:300] + "...")
#                         st.markdown("---")
#                 else:
#                     st.warning(f"No resume content found for {person_name}.")
#             else:
#                 st.error(f"No candidate found with name '{person_name}'.")
#         else:
#             # General resume search without candidate filter
#             hits = query_azure_ai_search(user_query)
#             st.subheader("Resume Search Results")
#             if hits:
#                 for h in hits:
#                     st.write(f"Candidate ID: {h['candidate_id']}, Score: {h['score']}")
#                     st.write(h['content'][:300] + "...")
#                     st.markdown("---")
#             else:
#                 st.warning("No resume search results found.")

#     if intent == "metadata_search":
#         col, val = extract_metadata_filter(user_query)
#         st.write(f"Extracted filter column: {col}, value: {val}")

#         if not col:
#             st.error("Could not detect metadata filter in your query.")
#         elif col not in ALLOWED_COLUMNS:
#             st.error(f"Column '{col}' is not allowed for filtering.")
#         else:
#             if val:
#                 # Normal filtered query
#                 results = query_azure_sql_db(ALLOWED_COLUMNS[col], val)
#             else:
#                 # No filter value: get all candidates but only select the column
#                 results = query_azure_sql_db_no_filter(ALLOWED_COLUMNS[col])

#             if results:
#                 st.subheader("Metadata Search Results")
#                 for r in results:
#                     st.json(r)
#             else:
#                 st.warning("No candidates found matching your filter.")