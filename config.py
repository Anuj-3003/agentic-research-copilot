"""
config.py
Central configuration, mirroring FinDocGPT's config.py pattern for consistency.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# FinDocGPT is called as an independently-deployed service, not imported as
# code -- point this at a real deployment once Phase 1 (deploy FinDocGPT
# publicly) is done. Defaults to the local dev server for now.
FINDOCGPT_API_URL = os.getenv("FINDOCGPT_API_URL", "http://localhost:8000")

LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_NUM_GPU = os.getenv("OLLAMA_NUM_GPU")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Self-Critic RETRY verdicts loop back to the Planner, capped to avoid an
# infinite loop on a persistently unsupported claim.
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
