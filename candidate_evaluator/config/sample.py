import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv(override=True)

print("Using API key:", os.getenv("OPENAI_API_KEY"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(resp.choices[0].message.content)
except Exception as e:
    print("API call failed:", e)