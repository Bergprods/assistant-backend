FROM python:3.11-slim
WORKDIR /app

# install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# copy project files
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy package source
COPY my_ai_assistant ./my_ai_assistant
COPY backend/app.py ./backend/app.py
# copy prompts used by the orchestrator (JSON schema + instructions)
COPY prompts ./prompts

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
