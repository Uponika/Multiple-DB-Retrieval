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
index_name = os.getenv("AZURE_SEARCH_INDEX")

server = os.getenv("server").strip()
database = os.getenv("database").strip()
sql_username = os.getenv("sql_username").strip()
password = os.getenv("password").strip()
driver = os.getenv("driver").strip()

client  = OpenAI(api_key =os.getenv("OPENAI_API_KEY"))

# IMPORTANT: adjust this to the actual metadata columns in your candidates table
ALLOWED_COLUMNS = {
    "status": "status",
    "location": "location",
    "name": "name",
    "email": "email",    
    "candidate_id": "candidate_id"    
}


def classify_query_intent_llm(query: str) -> str:
    prompt = f"""
        You are an intent classification assistant for a candidate search app.

        - resume_search: questions about skills, technologies, experiences, tools, programming languages, qualifications, certifications, or anything in the full resume text.
        - metadata_search: questions about fixed candidate attributes stored in metadata: name, email, phone, location, status, interview status, candidate ID.

        If the query asks about what a candidate knows, their skills, or experience, classify it as resume_search.

        Classify the following query into exactly one label: resume_search or metadata_search.

        Query: "{query}"
        Answer with exactly one word: resume_search or metadata_search.
        """
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an intent classification assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    intent = resp.choices[0].message.content.strip().lower()
    if intent not in ("resume_search", "metadata_search"):
        intent = "resume_search"
    return intent

def extract_metadata_filter(query: str) -> tuple:
    # 1. Try explicit 'col = val'
    explicit = re.search(r"([a-zA-Z0-9_ ]+)\s*=\s*['\"]?([^'\"]+)['\"]?", query)
    if explicit:
        col = explicit.group(1).strip().lower().replace(" ", "_")
        val = explicit.group(2).strip()
        return col, val

    # 2. Quick fallback for "from <location>"
    from_match = re.search(r"from ([a-zA-Z ]+)", query, re.IGNORECASE)
    if from_match:
        val = from_match.group(1).strip()
        return "location", val

    # 3. Heuristic for "give/list <column> of all candidates"
    all_cols_pattern = "|".join(ALLOWED_COLUMNS.keys())
    all_match = re.search(rf"(?:give|list|show|get)\s+({all_cols_pattern})\s+of\s+all\s+candidates", query, re.IGNORECASE)
    if all_match:
        col = all_match.group(1).strip().lower().replace(" ", "_")
        return col, None  # No filter value - means get column for all

    # 4. Fallback to LLM extraction (your existing code)...
    allowed_list = ", ".join(list(ALLOWED_COLUMNS.keys()))
    prompt = f"""
            Extract a single metadata filter from the user's query. Allowed columns: {allowed_list}.
            Return JSON ONLY with keys "column" and "value".
            If no usable filter found, return {{"column": null, "value": null}}.

            Examples:
            - "list all candidates from toronto" -> {{"column":"location","value":"Toronto"}}
            - "show candidates interviewed last month" -> {{"column":"status","value":"Interviewed"}}
            - "get emails of shortlisted candidates" -> {{"column":"status","value":"Shortlisted"}}

            Now extract from this query:
            "{query}"
            """
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a JSON extractor that returns a single filter."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    try:
        out = resp.choices[0].message.content.strip()
        parsed = json.loads(out)
    except Exception:
        try:
            parsed = json.loads(out.replace("'", '"'))
        except Exception:
            return None, None

    col = parsed.get("column")
    val = parsed.get("value")
    if col:
        col = col.strip().lower().replace(" ", "_")
    return col, val

def query_azure_ai_search(query_text: str, candidate_id: str = None) -> list:
    client_search = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(search_key)
    )
    # If candidate_id given, filter on it for exact resume search
    if candidate_id:
        results = client_search.search(
            search_text=query_text,
            filter=f"candidate_id eq '{candidate_id}'",
            top=5,
            select=["candidate_id", "content"]
        )
    else:
        results = client_search.search(
            search_text=query_text,
            top=5,
            select=["candidate_id", "content"]
        )
    hits = []
    for result in results:
        hits.append({
            "candidate_id": result.get("candidate_id"),
            "content": result.get("content", ""),
            "score": result.get("@search.score")
        })
    return hits

def query_azure_sql_db(filter_column: str, filter_value: str) -> list:
    connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()

    # Use LOWER(...) = LOWER(?) for case-insensitive
    sql = f"SELECT * FROM candidates WHERE LOWER({filter_column}) = LOWER(?)"
    cursor.execute(sql, filter_value)

    rows = cursor.fetchall()
    cols = [column[0] for column in cursor.description] if cursor.description else []
    results = [dict(zip(cols, row)) for row in rows]

    cursor.close()
    conn.close()
    return results

def get_candidate_id_by_name(name: str) -> str | None:
    connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()

    query = "SELECT candidate_id FROM candidates WHERE LOWER(name) = LOWER(?)"
    cursor.execute(query, name)

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row:
        return row[0]  # candidate_id
    return None


def query_azure_sql_db_no_filter(select_column: str) -> list:
    connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()

    # Sanitize column name to avoid SQL injection (only allowed columns)
    if select_column not in ALLOWED_COLUMNS.values():
        return []

    sql = f"SELECT {select_column} FROM candidates"
    cursor.execute(sql)

    rows = cursor.fetchall()
    cols = [column[0] for column in cursor.description] if cursor.description else []
    results = [dict(zip(cols, row)) for row in rows]

    cursor.close()
    conn.close()
    return results
# Streamlit UI
st.title("Candidate Search App")

user_query = st.text_input("Ask anything about candidates or resumes:")

if user_query:
    intent = classify_query_intent_llm(user_query)
    st.write(f"Detected intent: **{intent}**")

    if intent == "resume_search":
        # Detect "skills of Alice" style queries and extract name
        name_match = re.search(
        r"(?:skills|experience|resume|projects|worked) of ([a-zA-Z]+(?: [a-zA-Z]+)*)",
        user_query,
        re.IGNORECASE,
        )
        if name_match:
            person_name = name_match.group(1).strip("?.! ")
            candidate_id = get_candidate_id_by_name(person_name)
            if candidate_id:
                # Search Azure Cognitive Search, filtered to this candidate_id
                hits = query_azure_ai_search(user_query, candidate_id=candidate_id)
                st.subheader(f"Resume Search Results for {person_name}")
                if hits:
                    for h in hits:
                        st.write(f"Candidate ID: {h['candidate_id']}, Score: {h['score']}")
                        st.write(h['content'][:300] + "...")
                        st.markdown("---")
                else:
                    st.warning(f"No resume content found for {person_name}.")
            else:
                st.error(f"No candidate found with name '{person_name}'.")
        else:
            # General resume search without candidate filter
            hits = query_azure_ai_search(user_query)
            st.subheader("Resume Search Results")
            if hits:
                for h in hits:
                    st.write(f"Candidate ID: {h['candidate_id']}, Score: {h['score']}")
                    st.write(h['content'][:300] + "...")
                    st.markdown("---")
            else:
                st.warning("No resume search results found.")

    if intent == "metadata_search":
        col, val = extract_metadata_filter(user_query)
        st.write(f"Extracted filter column: {col}, value: {val}")

        if not col:
            st.error("Could not detect metadata filter in your query.")
        elif col not in ALLOWED_COLUMNS:
            st.error(f"Column '{col}' is not allowed for filtering.")
        else:
            if val:
                # Normal filtered query
                results = query_azure_sql_db(ALLOWED_COLUMNS[col], val)
            else:
                # No filter value: get all candidates but only select the column
                results = query_azure_sql_db_no_filter(ALLOWED_COLUMNS[col])

            if results:
                st.subheader("Metadata Search Results")
                for r in results:
                    st.json(r)
            else:
                st.warning("No candidates found matching your filter.")