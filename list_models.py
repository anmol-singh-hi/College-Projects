import os
from google import genai

client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY"),
    http_options={"api_version": "v1"}
)

for model in client.models.list():
    print(model.name)
