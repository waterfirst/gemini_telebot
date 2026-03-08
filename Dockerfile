FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Node.js 와 gwcli 설치 (선택 사항이지만 gws 도구를 위해)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @google/clasp # gwcli 의존성, 실제 gwcli는 프로젝트 구조에 따라 다름

COPY .env .
COPY tools.py .
COPY system_prompt.txt .
COPY cloud_run_bot.py .
CMD ["python", "cloud_run_bot.py"]
