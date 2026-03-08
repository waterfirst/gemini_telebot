import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

models = []
for m in genai.list_models():
    models.append(m.name)

with open("models.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(models))
print(f"Saved {len(models)} models to models.txt")
