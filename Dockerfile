# Phase 8: containerize the agent's FastAPI service.
#
# Note: this container runs the planning/orchestration layer only. It talks
# to FinDocGPT over HTTP (FINDOCGPT_API_URL) and, by default, to a local
# Ollama server (OLLAMA_BASE_URL) for the Planner/Self-Critic LLM calls --
# neither Ollama nor FinDocGPT run inside this image. Point FINDOCGPT_API_URL
# and OLLAMA_BASE_URL/LLM_BACKEND at real deployed services when running this
# container anywhere but localhost (see README's "Not built yet" section).
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
