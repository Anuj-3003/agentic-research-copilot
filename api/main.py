"""
api/main.py
Phase 8: exposes the agent over HTTP -- mirrors FinDocGPT's api/main.py
pattern (structured logging, basic rate limiting, Pydantic request model)
for consistency across the two repos.
"""
import json
import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from agent.graph import app as agent_graph
from agent.tracing import save_trace

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("agentic_research_copilot")

app = FastAPI(title="Agentic Research Copilot")

RATE_LIMIT_PER_MINUTE = 20
_request_log: dict[str, deque] = defaultdict(deque)


def check_rate_limit(client_ip: str):
    now = time.time()
    window = _request_log[client_ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded, try again shortly.")
    window.append(now)


class QueryRequest(BaseModel):
    question: str


@app.post("/query")
async def query(payload: QueryRequest, request: Request):
    check_rate_limit(request.client.host if request.client else "unknown")

    start = time.time()
    # ainvoke, not invoke: the graph has an async node (orchestrator), and
    # we're already inside FastAPI's running event loop here.
    result = await agent_graph.ainvoke({
        "question": payload.question,
        "plan": None,
        "tool_results": [],
        "draft_report": None,
        "critic_result": None,
        "retry_count": 0,
        "final_output": "",
        "trace": [],
    })
    latency = time.time() - start
    trace_path = save_trace(result)

    logger.info(json.dumps({
        "event": "query",
        "question": payload.question,
        "critic_verdict": result["critic_result"].verdict if result["critic_result"] else None,
        "retry_count": result["retry_count"],
        "num_tool_calls": len(result["tool_results"]),
        "latency_sec": round(latency, 2),
    }))

    return {
        "answer": result["final_output"],
        "plan": [s.model_dump() for s in result["plan"].steps] if result["plan"] else [],
        "critic_verdict": result["critic_result"].verdict if result["critic_result"] else None,
        "retry_count": result["retry_count"],
        "latency_sec": round(latency, 2),
        "trace_path": trace_path,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)
