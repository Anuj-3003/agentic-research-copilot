"""
agent/tools/findocgpt_tool.py
Async wrapper calling the deployed (or local dev) FinDocGPT API as a tool --
composition over duplication: this repo never re-implements retrieval.
"""
import httpx

from agent.schemas import FinDocGPTSource, FinDocGPTToolResponse
from config import FINDOCGPT_API_URL


async def call_findocgpt(question: str, timeout: float = 180.0) -> FinDocGPTToolResponse:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{FINDOCGPT_API_URL}/query", json={"question": question})
        resp.raise_for_status()
        data = resp.json()

    return FinDocGPTToolResponse(
        answer=data["answer"],
        sources=[FinDocGPTSource(**c) for c in data.get("citations", [])],
        confidence=data.get("confidence"),
    )
