
from dotenv import load_dotenv
import openai

import os
load_dotenv(override=True)

# Azure AI Search
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_API_KEY  = os.getenv("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX    = os.getenv("AZURE_SEARCH_INDEX")

# Azure SQL (single connection string recommended)
server = os.getenv("server").strip()
database = os.getenv("database").strip()
sql_username = os.getenv("sql_username").strip()
password = os.getenv("password").strip()
driver = os.getenv("driver").strip()

AZURE_SQL_CONN_STR    = connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

# OpenAI (or Azure OpenAI via langchain-openai if you prefer)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Optional: network timeouts
HTTP_TIMEOUT_SEC      = int(os.getenv("HTTP_TIMEOUT_SEC", "15"))

# Safety: allow public scraping? (True/False)
ALLOW_PUBLIC_SCRAPE   = "false"
