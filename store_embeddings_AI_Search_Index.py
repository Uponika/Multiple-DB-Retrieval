import os
import glob
import openai
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()

# OpenAI setup
openai.api_key = os.getenv("OPENAI_API_KEY")

# Azure AI Search setup
search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_SEARCH_API_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX")

search_client = SearchClient(endpoint=search_endpoint,
                              index_name=index_name,
                              credential=AzureKeyCredential(search_key))

resume_folder = os.getenv("RESUME_FOLDER")

def index_resumes():
    documents = []
    candidate_id = 1  # Starting ID

    for file_path in glob.glob(os.path.join(resume_folder, "*.txt")):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"Processing file: {file_path}")

        # Generate embedding from OpenAI
        embedding = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=content
        ).data[0].embedding

        print("Embeddings are", embedding)

        # Prepare document for Azure Search
        doc = {
            "candidate_id": str(candidate_id),
            "content": content,           
            "embedding": embedding
        }
        documents.append(doc)
        candidate_id += 1

    # Upload to Azure AI Search
    if documents:
        result = search_client.upload_documents(documents)
        print(f"Uploaded {len(result)} documents to Azure AI Search.")

if __name__ == "__main__":
    index_resumes()
