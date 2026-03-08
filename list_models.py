import os
import json
import google.generativeai as genai

with open("config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

genai.configure(api_key=cfg["gemini_api_key"])

models = []
for m in genai.list_models():
    models.append(m.name)

with open("models.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(models))
print(f"Saved {len(models)} models to models.txt")
