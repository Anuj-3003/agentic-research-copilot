"""
agent/llm.py
Same swappable-backend pattern as FinDocGPT's agent/llm.py -- Ollama by
default (free, local), Claude as an optional paid upgrade.
"""
from config import LLM_BACKEND, OLLAMA_MODEL, OLLAMA_BASE_URL, OLLAMA_NUM_GPU, ANTHROPIC_MODEL


def get_llm():
    if LLM_BACKEND == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=ANTHROPIC_MODEL)

    # langchain_ollama.ChatOllama (not langchain_community's) -- the
    # community version doesn't implement bind_tools(), which
    # with_structured_output() needs for the Planner's ExecutionPlan output.
    from langchain_ollama import ChatOllama
    kwargs = {"model": OLLAMA_MODEL, "base_url": OLLAMA_BASE_URL, "temperature": 0}
    if OLLAMA_NUM_GPU is not None:
        kwargs["num_gpu"] = int(OLLAMA_NUM_GPU)
    return ChatOllama(**kwargs)


llm = get_llm()
