import glob
import os
import openai
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import pyodbc
from dotenv import load_dotenv

load_dotenv()

# Azure SQL (single connection string recommended)
server = os.getenv("server").strip()
database = os.getenv("database").strip()
sql_username = os.getenv("sql_username").strip()
password = os.getenv("password").strip()
driver = os.getenv("driver").strip()

AZURE_SQL_CONN_STR    = connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

# Your DB connection setup (example)
def get_all_candidates():
    conn = pyodbc.connect(AZURE_SQL_CONN_STR)
    cursor = conn.cursor()
    cursor.execute("SELECT candidate_id, name FROM candidates")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {name: str(candidate_id) for candidate_id, name in rows}

openai.api_key = os.getenv("OPENAI_API_KEY")
search_key = os.getenv("AZURE_SEARCH_API_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX")

search_client = SearchClient(endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
                              index_name=index_name,
                              credential=AzureKeyCredential(search_key))

resume_folder = os.getenv("RESUME_FOLDER")
print("Resume folder is", resume_folder)

def index_resumes():
    candidate_map = get_all_candidates()  # {name: candidate_id UUID}
    documents = []

    for file_path in glob.glob(os.path.join(resume_folder, "*.txt")):
        filename = os.path.basename(file_path)
        candidate_name = os.path.splitext(filename)[0]  # assuming filename matches candidate name

        candidate_id = candidate_map.get(candidate_name)
        if not candidate_id:
            print(f"Skipping {candidate_name} as no candidate_id found in DB")
            continue

        print(f"Reading file: {file_path} for candidate_id: {candidate_id}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"Processing file: {file_path}")

        # Generate embedding from OpenAI
        embedding = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=content
        ).data[0].embedding

        doc = {
            "candidate_id": candidate_id,
            "content": content,           
            "embedding": embedding
        }
        documents.append(doc)

    if documents:
        result = search_client.upload_documents(documents)
        print(f"Uploaded {len(result)} documents to Azure AI Search.")

if __name__ == "__main__":
    index_resumes()
